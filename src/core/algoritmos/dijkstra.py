"""Dijkstra: rotas de emergência de menor custo."""

import math

from src.core.algoritmos.comum import exigir_vertices, reconstruir_caminho
from src.core.grafo import ErroGrafo, normalizar_numero
from src.core.heap_minimo import HeapMinimo

INFINITO_TEXTO = "∞"

COMPLEXIDADE = {
    "tempo": "O((V + E) log V)",
    "espaco": "O(V + E)",
    "explicacao": (
        "Cada aresta pode gerar uma inserção no heap, e cada inserção ou extração "
        "custa O(log E) = O(log V), pois E < V². Entradas antigas ficam no heap e "
        "são descartadas ao sair, por isso ele pode guardar O(E) itens."
    ),
}


def _exibir(distancia):
    return INFINITO_TEXTO if distancia == math.inf else normalizar_numero(distancia)


def dijkstra(grafo, origem, destino=None):
    """Calcula o menor custo da origem até cada vértice, usando o min-heap próprio.

    Pesos negativos são rejeitados: o algoritmo considera definitiva a distância de
    um vértice ao extraí-lo do heap, e uma aresta negativa encontrada depois poderia
    baratear esse caminho, invalidando a escolha gulosa.

    Empates de distância são resolvidos pela ordem alfabética dos vértices.

    Complexidade: O((V + E) log V) em tempo e O(V + E) de espaço adicional.
    """
    exigir_vertices(grafo, origem, destino)
    for de, para, peso in grafo.arestas():
        if peso < 0:
            raise ErroGrafo(
                f"Dijkstra não aceita pesos negativos (a aresta {de} e {para} tem peso {peso}). "
                "O algoritmo considera definitiva a distância de um vértice assim que o "
                "extrai do heap, e uma aresta negativa poderia baratear esse caminho depois."
            )

    vertices = grafo.vertices()
    indice = {v: i for i, v in enumerate(vertices)}
    distancias = {v: math.inf for v in vertices}
    predecessores = {v: None for v in vertices}
    distancias[origem] = 0

    heap = HeapMinimo()
    heap.inserir((0, indice[origem], origem))
    finalizados = set()
    ordem_finalizacao = []
    passos = []

    while not heap.esta_vazio():
        distancia, _, vertice = heap.extrair_minimo()
        if vertice in finalizados:
            continue
        finalizados.add(vertice)
        ordem_finalizacao.append(vertice)

        relaxacoes = []
        for vizinho, peso in grafo.vizinhos(vertice):
            if vizinho in finalizados:
                continue
            candidata = distancia + peso
            melhorou = candidata < distancias[vizinho]
            relaxacoes.append(
                {
                    "vizinho": vizinho,
                    "peso": peso,
                    "distancia_anterior": _exibir(distancias[vizinho]),
                    "distancia_candidata": _exibir(candidata),
                    "atualizou": melhorou,
                }
            )
            if melhorou:
                distancias[vizinho] = candidata
                predecessores[vizinho] = vertice
                heap.inserir((candidata, indice[vizinho], vizinho))
        passos.append(
            {
                "passo": len(passos) + 1,
                "vertice": vertice,
                "distancia": _exibir(distancia),
                "relaxacoes": relaxacoes,
            }
        )

    nao_alcancaveis = [v for v in vertices if v not in finalizados]
    tabela = [
        {
            "vertice": v,
            "distancia": _exibir(distancias[v]),
            "predecessor": predecessores[v],
            "caminho": reconstruir_caminho(predecessores, v),
        }
        for v in ordem_finalizacao
    ] + [
        {"vertice": v, "distancia": INFINITO_TEXTO, "predecessor": None, "caminho": []}
        for v in nao_alcancaveis
    ]

    caminho_destino = None
    if destino is not None:
        alcancavel = destino in finalizados
        caminho_destino = {
            "destino": destino,
            "alcancavel": alcancavel,
            "caminho": reconstruir_caminho(predecessores, destino) if alcancavel else [],
            "custo": _exibir(distancias[destino]),
        }

    return {
        "algoritmo": "dijkstra",
        "origem": origem,
        "tabela": tabela,
        "passos": passos,
        "nao_alcancaveis": nao_alcancaveis,
        "caminho_destino": caminho_destino,
        "complexidade": COMPLEXIDADE,
        "avisos": grafo.avisos(),
    }
