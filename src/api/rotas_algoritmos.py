"""Rotas de execução dos algoritmos."""

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StrictStr

from src.api.rotas_grafo import GrafoEntrada, construir_grafo
from src.core.algoritmos.bfs import bfs
from src.core.algoritmos.dfs import dfs
from src.core.algoritmos.dijkstra import dijkstra
from src.core.algoritmos.kruskal import kruskal

roteador = APIRouter(prefix="/api/algoritmos")

EXECUTORES = {
    "dfs": lambda grafo, origem, destino: dfs(grafo, origem),
    "bfs": bfs,
    "dijkstra": dijkstra,
    "kruskal": lambda grafo, origem, destino: kruskal(grafo),
}


class ExecucaoEntrada(BaseModel):
    grafo: GrafoEntrada
    origem: StrictStr | None = None
    destino: StrictStr | None = None


@roteador.post("/{algoritmo}")
def executar(algoritmo: str, entrada: ExecucaoEntrada):
    executor = EXECUTORES.get(algoritmo)
    if executor is None:
        raise HTTPException(status_code=404, detail=f"Algoritmo desconhecido: {algoritmo}.")
    grafo = construir_grafo(entrada.grafo)
    inicio = time.perf_counter()
    resultado = executor(grafo, entrada.origem, entrada.destino or None)
    tempo_ms = (time.perf_counter() - inicio) * 1000
    return {**resultado, "tempo_ms": round(tempo_ms, 3)}
