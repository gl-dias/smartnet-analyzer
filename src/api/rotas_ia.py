"""Rotas de linguagem natural. Nenhuma delas altera o grafo: quem aplica é o front, após a revisão."""

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictBool, StrictStr
from starlette.background import BackgroundTask

from src.api.rotas_grafo import GrafoEntrada, construir_grafo, descrever_estrutura
from src.auth.rate_limit import LimitadorTaxa
from src.core.grafo import ListaAdjacencia
from src.db import supabase_rest
from src.ia.interpretador import ErroIA, Operacao, interpretar, simular

MAXIMO_CARACTERES = 2000
MAXIMO_OPERACOES = 300
# O grafo vai como contexto em cada chamada: sem este teto, o custo não teria limite.
MAXIMO_VERTICES_CONTEXTO = 200
MAXIMO_ARESTAS_CONTEXTO = 1000
CHAMADAS_POR_HORA = 30

roteador = APIRouter(prefix="/api")
limitador_ia = LimitadorTaxa(CHAMADAS_POR_HORA, 60 * 60)


class InterpretarEntrada(BaseModel):
    texto: StrictStr
    canal: Literal["texto", "voz"] = "texto"
    grafo: GrafoEntrada


class PreviaEntrada(BaseModel):
    grafo: GrafoEntrada
    operacoes: list[Operacao] = Field(max_length=MAXIMO_OPERACOES)


class DecisaoEntrada(BaseModel):
    aceito: StrictBool


def _resposta_simulada(dados, operacoes):
    simulado = simular(dados, operacoes)
    grafo = ListaAdjacencia.from_json(simulado["grafo"])
    return {
        "tipo": "operacoes",
        "operacoes": simulado["operacoes"],
        "grafo": simulado["grafo"],
        "estrutura": descrever_estrutura(grafo),
    }


@roteador.post("/interpretar")
def rota_interpretar(entrada: InterpretarEntrada, request: Request, tarefas: BackgroundTasks):
    texto = entrada.texto.strip()
    if not texto:
        raise HTTPException(status_code=422, detail="Escreva o que deseja fazer no mapa.")
    if len(texto) > MAXIMO_CARACTERES:
        raise HTTPException(
            status_code=422, detail=f"O texto aceita no máximo {MAXIMO_CARACTERES} caracteres."
        )
    if (
        len(entrada.grafo.vertices) > MAXIMO_VERTICES_CONTEXTO
        or len(entrada.grafo.arestas) > MAXIMO_ARESTAS_CONTEXTO
    ):
        raise HTTPException(
            status_code=422,
            detail="Este grafo é grande demais para a IA. Use as abas Manual, Texto ou Importar/Exemplos.",
        )
    construir_grafo(entrada.grafo)
    if not limitador_ia.permitir(request.session.get("id", request.session["usuario"])):
        raise HTTPException(
            status_code=429,
            detail=f"Limite de {CHAMADAS_POR_HORA} interpretações por hora atingido. Use as demais abas.",
        )

    dados = entrada.grafo.model_dump(exclude_none=True)
    interpretacao_id = str(uuid.uuid4())
    # Toda chamada à IA fica registrada para auditoria, inclusive as que não geram operações.
    auditoria = (
        supabase_rest.registrar_sem_falhar,
        supabase_rest.registrar_interpretacao,
        interpretacao_id,
        request.session.get("id"),
        texto,
        entrada.canal,
    )
    try:
        resultado = interpretar(texto, entrada.canal, dados)
    except ErroIA as erro:
        # A auditoria acompanha a resposta, pois uma exceção cancelaria as tarefas da rota.
        return JSONResponse(
            status_code=503,
            content={"erro": str(erro)},
            background=BackgroundTask(*auditoria, {"erro": str(erro)}),
        )
    if resultado["tipo"] == "pergunta":
        tarefas.add_task(*auditoria, {"pergunta": resultado["pergunta"]})
        return resultado
    resposta = _resposta_simulada(dados, resultado["operacoes"])
    tarefas.add_task(*auditoria, resposta["operacoes"])
    return {**resposta, "interpretacao_id": interpretacao_id}


@roteador.post("/interpretacoes/{interpretacao_id}/decisao")
def rota_decisao(interpretacao_id: uuid.UUID, entrada: DecisaoEntrada, tarefas: BackgroundTasks):
    """Registra se o usuário confirmou ou cancelou a revisão."""
    tarefas.add_task(
        supabase_rest.registrar_sem_falhar,
        supabase_rest.marcar_interpretacao,
        interpretacao_id,
        entrada.aceito,
    )
    return {"ok": True}


@roteador.post("/operacoes/previa")
def rota_previa(entrada: PreviaEntrada):
    """Revalida as operações marcadas na tela de revisão e devolve o grafo resultante."""
    return _resposta_simulada(entrada.grafo.model_dump(exclude_none=True), entrada.operacoes)
