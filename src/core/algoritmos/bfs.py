"""Busca em largura: propagação de alertas pela cidade."""

from src.core.algoritmos.comum import exigir_vertices, reconstruir_caminho

COMPLEXIDADE = {
    "tempo": "O(V + E)",
    "espaco": "O(V)",
    "explicacao": (
        "Cada vértice entra e sai da fila uma única vez, e cada lista de "
        "adjacência é percorrida uma única vez. A fila usa um índice de início, "
        "então remover é O(1). A tabela de passos existe só para exibição: copiar "
        "a fila a cada passo soma até O(V²) e não faz parte do algoritmo em si."
    ),
}


def bfs(grafo, origem, destino=None):
    """Executa a BFS a partir de origem, enfileirando vizinhos em ordem alfabética.

    Em grafos sem peso, o nível de um vértice é o menor número de saltos até ele,
    porque a fila processa todos os vértices de um nível antes dos do nível seguinte.

    Complexidade: O(V + E) em tempo e O(V) de espaço adicional.
    """
    exigir_vertices(grafo, origem, destino)

    fila = [origem]
    inicio = 0
    niveis = {origem: 0}
    predecessores = {origem: None}
    passos = []
    while inicio < len(fila):
        vertice = fila[inicio]
        inicio += 1
        enfileirados = []
        for vizinho, _ in grafo.vizinhos(vertice):
            if vizinho not in niveis:
                niveis[vizinho] = niveis[vertice] + 1
                predecessores[vizinho] = vertice
                fila.append(vizinho)
                enfileirados.append(vizinho)
        passos.append(
            {
                "passo": len(passos) + 1,
                "removido": vertice,
                "enfileirados": enfileirados,
                "fila": fila[inicio:],
            }
        )

    caminho_destino = None
    if destino is not None:
        alcancavel = destino in niveis
        caminho_destino = {
            "destino": destino,
            "alcancavel": alcancavel,
            "caminho": reconstruir_caminho(predecessores, destino) if alcancavel else [],
            "saltos": niveis.get(destino),
        }

    vertices = grafo.vertices()
    return {
        "algoritmo": "bfs",
        "origem": origem,
        "ordem_visita": fila,
        "passos": passos,
        "tabela": [
            {"vertice": v, "nivel": niveis.get(v), "predecessor": predecessores.get(v)}
            for v in vertices
        ],
        "nao_alcancaveis": [v for v in vertices if v not in niveis],
        "caminho_destino": caminho_destino,
        "complexidade": COMPLEXIDADE,
        "avisos": grafo.avisos(),
    }
