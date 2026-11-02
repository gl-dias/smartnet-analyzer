"""Rotas de estrutura do grafo e de exemplos."""

import json
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StrictStr

from src.core.grafo import ListaAdjacencia
from src.db import supabase_rest

PASTA_EXEMPLOS = Path(__file__).resolve().parent.parent.parent / "exemplos"
EXEMPLOS = ("grafo_enunciado", "grafo_direcionado", "grafo_sem_peso", "grafo_desconexo")

MAXIMO_VERTICES = 2000
MAXIMO_ARESTAS = 10000
MAXIMO_NOME_GRAFO = 100

roteador = APIRouter(prefix="/api")


class ArestaEntrada(BaseModel):
    origem: StrictStr | StrictInt
    destino: StrictStr | StrictInt
    peso: StrictInt | StrictFloat | None = None


class GrafoEntrada(BaseModel):
    direcionado: StrictBool = False
    ponderado: StrictBool = True
    vertices: list[StrictStr | StrictInt] = Field(default_factory=list, max_length=MAXIMO_VERTICES)
    arestas: list[ArestaEntrada] = Field(default_factory=list, max_length=MAXIMO_ARESTAS)


class SalvarEntrada(BaseModel):
    nome: StrictStr
    grafo: GrafoEntrada
    origem_entrada: Literal["manual", "texto", "linguagem_natural", "voz", "exemplo", "importacao"]


def construir_grafo(entrada: GrafoEntrada) -> ListaAdjacencia:
    """Reconstrói a lista de adjacência a partir do grafo enviado pelo front."""
    return ListaAdjacencia.from_json(entrada.model_dump(exclude_none=True))


def descrever_estrutura(grafo: ListaAdjacencia) -> dict:
    dump = grafo.para_dict()
    return {
        # Lista, e não objeto, porque o JavaScript reordena chaves numéricas de objetos.
        "lista_adjacencia": [
            {"vertice": vertice, "vizinhos": dump[vertice]} for vertice in grafo.vertices()
        ],
        "vertices": grafo.vertices(),
        "estatisticas": {
            "vertices": grafo.numero_vertices(),
            "arestas": grafo.numero_arestas(),
            "densidade": grafo.densidade(),
        },
        "avisos": grafo.avisos(),
    }


@roteador.post("/estrutura")
def estrutura(entrada: GrafoEntrada):
    return descrever_estrutura(construir_grafo(entrada))


@roteador.get("/grafos")
def listar_grafos():
    return {"grafos": supabase_rest.listar_grafos()}


@roteador.post("/grafos", status_code=201)
def salvar_grafo(entrada: SalvarEntrada, request: Request):
    nome = entrada.nome.strip()
    if not nome:
        raise HTTPException(status_code=422, detail="Dê um nome ao grafo.")
    if len(nome) > MAXIMO_NOME_GRAFO:
        raise HTTPException(
            status_code=422, detail=f"O nome aceita no máximo {MAXIMO_NOME_GRAFO} caracteres."
        )
    grafo = construir_grafo(entrada.grafo)
    if not grafo.numero_vertices():
        raise HTTPException(status_code=422, detail="O grafo está vazio: não há o que salvar.")
    # O sentido e os pesos ficam como o usuário inseriu, inclusive os ocultos em grafo sem peso.
    dados = {**entrada.grafo.model_dump(exclude_none=True), "vertices": grafo.vertices()}
    return supabase_rest.salvar_grafo(
        request.session.get("id"), nome, dados, entrada.origem_entrada
    )


@roteador.get("/grafos/{grafo_id}")
def carregar_grafo(grafo_id: uuid.UUID):
    linha = supabase_rest.buscar_grafo(grafo_id)
    if linha is None:
        raise HTTPException(status_code=404, detail="Grafo não encontrado.")
    return linha


@roteador.delete("/grafos/{grafo_id}")
def apagar_grafo(grafo_id: uuid.UUID):
    if not supabase_rest.apagar_grafo(grafo_id):
        raise HTTPException(status_code=404, detail="Grafo não encontrado.")
    return {"ok": True}


@roteador.get("/exemplos/{nome}")
def exemplo(nome: str):
    if nome not in EXEMPLOS:
        raise HTTPException(status_code=404, detail="Exemplo não encontrado.")
    return json.loads((PASTA_EXEMPLOS / f"{nome}.json").read_text(encoding="utf-8"))
