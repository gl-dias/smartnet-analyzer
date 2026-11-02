"""Kruskal: rede de fibra ótica de menor custo."""

from src.core.grafo import normalizar_numero
from src.core.ordenacao import merge_sort
from src.core.union_find import UnionFind

COMPLEXIDADE = {
    "tempo": "O(E log E)",
    "espaco": "O(V + E)",
    "explicacao": (
        "Ordenar as arestas com merge sort custa O(E log E). Depois, cada aresta "
        "faz operações de Union-Find em O(α(V)) amortizado, um custo dominado pela "
        "ordenação. Como E < V², O(E log E) equivale a O(E log V)."
    ),
}


def kruskal(grafo):
    """Calcula a árvore geradora mínima (ou floresta, se o grafo for desconexo).

    Processa as arestas da mais barata para a mais cara e aceita cada uma que une
    dois componentes diferentes. Rejeita as que formariam ciclo. Empates de peso
    seguem a ordem alfabética das arestas, pois o merge sort é estável. Em empates,
    as arestas escolhidas podem variar, mas o custo total é sempre o mesmo.

    Todas as arestas são examinadas, sem parar na (V - 1)-ésima aceita, para que a
    tabela de passos mostre também as rejeitadas.

    Complexidade: O(E log E) em tempo e O(V + E) de espaço adicional.
    """
    avisos = grafo.avisos()
    if grafo.direcionado:
        avisos.append(
            "A árvore geradora mínima é definida para grafos não direcionados. "
            "Kruskal foi executado ignorando a direção das arestas."
        )
    if not grafo.ponderado:
        avisos.append("Grafo sem peso: cada aresta foi considerada com custo 1.")

    conjuntos = UnionFind(grafo.vertices())
    selecionadas = []
    passos = []
    custo_total = 0
    for origem, destino, peso in merge_sort(grafo.arestas(), chave=lambda aresta: aresta[2]):
        aceita = conjuntos.unir(origem, destino)
        passos.append(
            {
                "passo": len(passos) + 1,
                "origem": origem,
                "destino": destino,
                "peso": peso,
                "aceita": aceita,
                "motivo": "Une dois componentes" if aceita else "Formaria ciclo",
            }
        )
        if aceita:
            selecionadas.append({"origem": origem, "destino": destino, "peso": peso})
            custo_total += peso

    componentes = conjuntos.total_conjuntos
    floresta = componentes > 1
    if floresta:
        avisos.append(
            f"O grafo é desconexo ({componentes} componentes): o resultado é uma "
            "floresta geradora mínima, não uma árvore."
        )

    return {
        "algoritmo": "kruskal",
        "passos": passos,
        "arestas_selecionadas": selecionadas,
        "custo_total": normalizar_numero(custo_total),
        "componentes": componentes,
        "floresta": floresta,
        "complexidade": COMPLEXIDADE,
        "avisos": avisos,
    }
