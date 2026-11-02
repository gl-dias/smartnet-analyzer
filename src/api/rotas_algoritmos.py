"""Rotas de execução dos algoritmos."""

import time
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, StrictStr

from src.api.rotas_grafo import GrafoEntrada, construir_grafo
from src.core.algoritmos.bfs import bfs
from src.core.algoritmos.dfs import dfs
from src.core.algoritmos.dijkstra import dijkstra
from src.core.algoritmos.kruskal import kruskal
from src.db import supabase_rest

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
    # Presente quando o grafo atual é um grafo salvo, sem alterações desde então.
    grafo_id: uuid.UUID | None = None


@roteador.post("/{algoritmo}")
def executar(algoritmo: str, entrada: ExecucaoEntrada, tarefas: BackgroundTasks):
    executor = EXECUTORES.get(algoritmo)
    if executor is None:
        raise HTTPException(status_code=404, detail=f"Algoritmo desconhecido: {algoritmo}.")
    grafo = construir_grafo(entrada.grafo)
    inicio = time.perf_counter()
    resultado = executor(grafo, entrada.origem, entrada.destino or None)
    tempo_ms = round((time.perf_counter() - inicio) * 1000, 3)
    tarefas.add_task(
        supabase_rest.registrar_sem_falhar,
        supabase_rest.registrar_execucao,
        str(entrada.grafo_id) if entrada.grafo_id else None,
        algoritmo,
        {"origem": entrada.origem, "destino": entrada.destino or None},
        {chave: valor for chave, valor in resultado.items() if chave != "complexidade"},
        tempo_ms,
    )
    return {**resultado, "tempo_ms": tempo_ms}
