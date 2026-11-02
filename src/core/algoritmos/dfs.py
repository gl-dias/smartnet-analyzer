"""Busca em profundidade: auditoria de rotas, conectividade e becos sem saída."""

from src.core.algoritmos.comum import exigir_vertices

COMPLEXIDADE = {
    "tempo": "O(V + E)",
    "espaco": "O(V)",
    "explicacao": (
        "Cada vértice é descoberto e finalizado uma única vez, e cada lista de "
        "adjacência é percorrida uma única vez. A análise de conectividade faz "
        "um número constante de percursos, logo mantém O(V + E)."
    ),
}


def _explorar(vizinhos_de, inicio, visitados):
    """Percorre em profundidade a partir de inicio, com pilha explícita.

    Visita na mesma ordem da versão recursiva, sem correr o risco de estourar o
    limite de recursão do Python em grafos com caminhos longos. Devolve os
    eventos na ordem em que ocorreram: (tipo, vértice, pai).
    """
    visitados.add(inicio)
    eventos = [("descoberta", inicio, None)]
    pilha = [(inicio, iter(vizinhos_de(inicio)))]
    while pilha:
        vertice, restantes = pilha[-1]
        for vizinho in restantes:
            if vizinho not in visitados:
                visitados.add(vizinho)
                eventos.append(("descoberta", vizinho, vertice))
                pilha.append((vizinho, iter(vizinhos_de(vizinho))))
                break
        else:
            pilha.pop()
            eventos.append(("finalizacao", vertice, None))
    return eventos


def _arvore_em_texto(raiz, filhos):
    """Desenha a árvore DFS no estilo de árvore de diretórios. O(V)."""
    linhas = [raiz]
    pilha = [(filho, "", i == len(filhos[raiz]) - 1) for i, filho in enumerate(filhos[raiz])]
    pilha.reverse()
    while pilha:
        vertice, prefixo, e_ultimo = pilha.pop()
        linhas.append(f"{prefixo}{'└── ' if e_ultimo else '├── '}{vertice}")
        prefixo_filhos = prefixo + ("    " if e_ultimo else "│   ")
        netos = filhos[vertice]
        for i in range(len(netos) - 1, -1, -1):
            pilha.append((netos[i], prefixo_filhos, i == len(netos) - 1))
    return "\n".join(linhas)


def _agrupar(vertices, rotulo):
    """Agrupa vértices por rótulo mantendo a ordem alfabética, em O(V), sem ordenar."""
    grupos = {}
    for vertice in vertices:
        grupos.setdefault(rotulo[vertice], []).append(vertice)
    return list(grupos.values())


def _componentes(vertices, vizinhos_de):
    """Componentes alcançados por percursos sucessivos sobre vizinhos_de. O(V + E)."""
    visitados = set()
    rotulo = {}
    for inicio in vertices:
        if inicio not in visitados:
            for tipo, vertice, _ in _explorar(vizinhos_de, inicio, visitados):
                if tipo == "descoberta":
                    rotulo[vertice] = inicio
    return _agrupar(vertices, rotulo)


def _componentes_fortes(vertices, saida, entrada):
    """Algoritmo de Kosaraju, O(V + E).

    Um percurso no grafo original fornece a ordem de finalização. Percorrendo o
    grafo transposto na ordem inversa de finalização, cada percurso cobre
    exatamente um componente fortemente conexo.
    """
    visitados = set()
    finalizacao = []
    for inicio in vertices:
        if inicio not in visitados:
            for tipo, vertice, _ in _explorar(saida.__getitem__, inicio, visitados):
                if tipo == "finalizacao":
                    finalizacao.append(vertice)
    visitados = set()
    rotulo = {}
    for inicio in reversed(finalizacao):
        if inicio not in visitados:
            for tipo, vertice, _ in _explorar(entrada.__getitem__, inicio, visitados):
                if tipo == "descoberta":
                    rotulo[vertice] = inicio
    return _agrupar(vertices, rotulo)


def analisar_conectividade(grafo):
    """Classifica a conectividade do grafo inteiro, independente da origem. O(V + E)."""
    vertices = grafo.vertices()
    saida = {v: [vizinho for vizinho, _ in grafo.vizinhos(v)] for v in vertices}

    if not grafo.direcionado:
        componentes = _componentes(vertices, saida.__getitem__)
        conexo = len(componentes) == 1
        return {
            "conexo": conexo,
            "classificacao": "Conexo" if conexo else f"Desconexo ({len(componentes)} componentes)",
            "componentes": componentes,
        }

    entrada = {v: [] for v in vertices}
    for vertice in vertices:
        for vizinho in saida[vertice]:
            entrada[vizinho].append(vertice)
    sem_direcao = {v: saida[v] + entrada[v] for v in vertices}

    componentes_fracas = _componentes(vertices, sem_direcao.__getitem__)
    componentes_fortes = _componentes_fortes(vertices, saida, entrada)
    fortemente = len(componentes_fortes) == 1
    fracamente = len(componentes_fracas) == 1
    if fortemente:
        classificacao = "Fortemente conexo"
    elif fracamente:
        classificacao = "Fracamente conexo"
    else:
        classificacao = f"Desconexo ({len(componentes_fracas)} componentes)"
    return {
        "conexo": fracamente,
        "fortemente_conexo": fortemente,
        "fracamente_conexo": fracamente,
        "classificacao": classificacao,
        "componentes": componentes_fracas,
        "componentes_fortes": componentes_fortes,
    }


def _becos_sem_saida(grafo):
    """Direcionado: sem arestas de saída. Não direcionado: grau 1. Self-loops não contam."""
    becos = []
    for vertice in grafo.vertices():
        saidas = sum(1 for vizinho, _ in grafo.vizinhos(vertice) if vizinho != vertice)
        if saidas == 0 if grafo.direcionado else saidas == 1:
            becos.append(vertice)
    return becos


def dfs(grafo, origem):
    """Executa a DFS a partir de origem, visitando vizinhos em ordem alfabética.

    Complexidade: O(V + E) em tempo e O(V) de espaço adicional.
    """
    exigir_vertices(grafo, origem)

    visitados = set()
    eventos = _explorar(
        lambda vertice: [vizinho for vizinho, _ in grafo.vizinhos(vertice)], origem, visitados
    )

    ordem_visita = []
    predecessores = {}
    filhos = {}
    descoberta = {}
    finalizacao = {}
    relogio = 0
    for tipo, vertice, pai in eventos:
        relogio += 1
        if tipo == "descoberta":
            ordem_visita.append(vertice)
            predecessores[vertice] = pai
            filhos[vertice] = []
            descoberta[vertice] = relogio
            if pai is not None:
                filhos[pai].append(vertice)
        else:
            finalizacao[vertice] = relogio

    vertices = grafo.vertices()
    return {
        "algoritmo": "dfs",
        "origem": origem,
        "ordem_visita": ordem_visita,
        "arvore_texto": _arvore_em_texto(origem, filhos),
        "arestas_arvore": [
            {"origem": predecessores[v], "destino": v} for v in ordem_visita[1:]
        ],
        "tabela": [
            {
                "vertice": v,
                "predecessor": predecessores.get(v),
                "descoberta": descoberta.get(v),
                "finalizacao": finalizacao.get(v),
            }
            for v in vertices
        ],
        "nao_alcancaveis": [v for v in vertices if v not in visitados],
        "becos_sem_saida": _becos_sem_saida(grafo),
        "conectividade": analisar_conectividade(grafo),
        "complexidade": COMPLEXIDADE,
        "avisos": grafo.avisos(),
    }
