"""Rotas de estrutura do grafo e de exemplos."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StrictStr

from src.core.grafo import ListaAdjacencia

PASTA_EXEMPLOS = Path(__file__).resolve().parent.parent.parent / "exemplos"
EXEMPLOS = ("grafo_enunciado", "grafo_direcionado", "grafo_sem_peso", "grafo_desconexo")

MAXIMO_VERTICES = 2000
MAXIMO_ARESTAS = 10000

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


def construir_grafo(entrada: GrafoEntrada) -> ListaAdjacencia:
    """Reconstrói a lista de adjacência a partir do grafo enviado pelo front."""
    return ListaAdjacencia.from_json(entrada.model_dump(exclude_none=True))


@roteador.post("/estrutura")
def estrutura(entrada: GrafoEntrada):
    grafo = construir_grafo(entrada)
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


@roteador.get("/exemplos/{nome}")
def exemplo(nome: str):
    if nome not in EXEMPLOS:
        raise HTTPException(status_code=404, detail="Exemplo não encontrado.")
    return json.loads((PASTA_EXEMPLOS / f"{nome}.json").read_text(encoding="utf-8"))
