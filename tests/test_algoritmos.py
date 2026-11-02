"""Testes dos quatro algoritmos, incluindo os resultados esperados do enunciado."""

import json
import math
import random
from pathlib import Path

import pytest

from src.core.algoritmos.bfs import bfs
from src.core.algoritmos.dfs import analisar_conectividade, dfs
from src.core.algoritmos.dijkstra import dijkstra
from src.core.algoritmos.kruskal import kruskal
from src.core.grafo import ErroGrafo, ListaAdjacencia

EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"


def carregar(nome):
    return ListaAdjacencia.from_json((EXEMPLOS / f"{nome}.json").read_text(encoding="utf-8"))


def distancias(resultado):
    return {linha["vertice"]: linha["distancia"] for linha in resultado["tabela"]}


def coluna(resultado, campo):
    return {linha["vertice"]: linha[campo] for linha in resultado["tabela"]}


# Grafo do enunciado


@pytest.fixture
def enunciado():
    return carregar("grafo_enunciado")


def test_enunciado_estrutura(enunciado):
    assert enunciado.numero_vertices() == 8
    assert enunciado.numero_arestas() == 14
    assert [v for v, _ in enunciado.vizinhos("A")] == ["B", "D", "F", "O"]


def test_enunciado_dfs(enunciado):
    resultado = dfs(enunciado, "O")
    assert resultado["ordem_visita"] == ["O", "A", "B", "C", "E", "D", "T", "F"]
    assert resultado["nao_alcancaveis"] == []
    assert resultado["conectividade"]["conexo"] is True
    assert resultado["becos_sem_saida"] == []


def test_enunciado_dfs_arvore_e_predecessores(enunciado):
    resultado = dfs(enunciado, "O")
    assert resultado["arvore_texto"].splitlines() == [
        "O",
        "└── A",
        "    └── B",
        "        └── C",
        "            └── E",
        "                └── D",
        "                    └── T",
        "                        └── F",
    ]
    predecessores = coluna(resultado, "predecessor")
    assert predecessores["O"] is None
    assert predecessores["D"] == "E"
    assert predecessores["F"] == "T"


def test_enunciado_dfs_tempos(enunciado):
    resultado = dfs(enunciado, "O")
    descoberta = coluna(resultado, "descoberta")
    finalizacao = coluna(resultado, "finalizacao")
    # O caminho é linear: descobre de 1 a 8 e finaliza de 9 a 16, na ordem inversa.
    assert [descoberta[v] for v in resultado["ordem_visita"]] == list(range(1, 9))
    assert [finalizacao[v] for v in reversed(resultado["ordem_visita"])] == list(range(9, 17))


def test_enunciado_bfs(enunciado):
    resultado = bfs(enunciado, "O", "T")
    assert resultado["ordem_visita"] == ["O", "A", "B", "C", "D", "F", "E", "T"]
    assert coluna(resultado, "nivel") == {
        "O": 0, "A": 1, "B": 1, "C": 1, "D": 2, "F": 2, "E": 2, "T": 3,
    }
    assert resultado["caminho_destino"]["caminho"] == ["O", "A", "D", "T"]
    assert resultado["caminho_destino"]["saltos"] == 3


def test_enunciado_bfs_tabela_passo_a_passo(enunciado):
    passos = bfs(enunciado, "O")["passos"]
    assert passos[0] == {
        "passo": 1, "removido": "O", "enfileirados": ["A", "B", "C"], "fila": ["A", "B", "C"],
    }
    assert passos[1] == {
        "passo": 2, "removido": "A", "enfileirados": ["D", "F"], "fila": ["B", "C", "D", "F"],
    }
    assert passos[-1]["fila"] == []
    assert len(passos) == 8


def test_enunciado_dijkstra(enunciado):
    resultado = dijkstra(enunciado, "O", "T")
    assert distancias(resultado) == {
        "O": 0, "A": 2, "B": 4, "C": 4, "E": 7, "D": 8, "T": 13, "F": 14,
    }
    assert [linha["vertice"] for linha in resultado["tabela"]] == [
        "O", "A", "B", "C", "E", "D", "T", "F",
    ]
    assert coluna(resultado, "caminho")["T"] == ["O", "A", "B", "D", "T"]
    assert coluna(resultado, "caminho")["F"] == ["O", "A", "F"]
    assert resultado["caminho_destino"]["custo"] == 13


def test_enunciado_dijkstra_registra_relaxacoes(enunciado):
    primeiro = dijkstra(enunciado, "O")["passos"][0]
    assert primeiro["vertice"] == "O"
    assert primeiro["relaxacoes"][0] == {
        "vizinho": "A", "peso": 2, "distancia_anterior": "∞",
        "distancia_candidata": 2, "atualizou": True,
    }


def test_enunciado_kruskal(enunciado):
    resultado = kruskal(enunciado)
    assert resultado["custo_total"] == 20
    assert len(resultado["arestas_selecionadas"]) == 7
    assert resultado["floresta"] is False
    assert resultado["avisos"] == []
    assert len(resultado["passos"]) == 14
    pesos = [passo["peso"] for passo in resultado["passos"]]
    assert pesos == sorted(pesos)
    assert sum(passo["aceita"] for passo in resultado["passos"]) == 7


def test_resultados_sao_serializaveis_em_json(enunciado):
    for resultado in [dfs(enunciado, "O"), bfs(enunciado, "O"), dijkstra(enunciado, "O"), kruskal(enunciado)]:
        json.dumps(resultado, allow_nan=False)
        assert resultado["complexidade"]["tempo"].startswith("O(")


# Grafo direcionado


@pytest.fixture
def direcionado():
    return carregar("grafo_direcionado")


def test_direcionado_dfs_respeita_o_sentido(direcionado):
    resultado = dfs(direcionado, "O")
    assert resultado["ordem_visita"] == ["O", "A", "B", "C", "D", "F"]
    assert resultado["nao_alcancaveis"] == ["E"]
    assert resultado["becos_sem_saida"] == ["F"]


def test_direcionado_conectividade(direcionado):
    conectividade = analisar_conectividade(direcionado)
    assert conectividade["fracamente_conexo"] is True
    assert conectividade["fortemente_conexo"] is False
    assert conectividade["classificacao"] == "Fracamente conexo"
    assert ["B", "C", "D"] in conectividade["componentes_fortes"]
    assert len(conectividade["componentes_fortes"]) == 5


def test_fortemente_conexo():
    grafo = ListaAdjacencia(direcionado=True, ponderado=False)
    for de, para in [("A", "B"), ("B", "C"), ("C", "A")]:
        grafo.adicionar_aresta(de, para)
    assert analisar_conectividade(grafo)["classificacao"] == "Fortemente conexo"


def test_direcionado_desconexo():
    grafo = ListaAdjacencia(direcionado=True, ponderado=False)
    grafo.adicionar_aresta("A", "B")
    grafo.adicionar_aresta("C", "D")
    conectividade = analisar_conectividade(grafo)
    assert conectividade["fracamente_conexo"] is False
    assert conectividade["componentes"] == [["A", "B"], ["C", "D"]]


def test_direcionado_bfs(direcionado):
    resultado = bfs(direcionado, "O", "E")
    assert resultado["ordem_visita"] == ["O", "A", "C", "B", "D", "F"]
    assert resultado["nao_alcancaveis"] == ["E"]
    assert resultado["caminho_destino"] == {
        "destino": "E", "alcancavel": False, "caminho": [], "saltos": None,
    }


def test_direcionado_dijkstra(direcionado):
    resultado = dijkstra(direcionado, "O", "E")
    assert distancias(resultado) == {
        "O": 0, "A": 2, "C": 4, "B": 5, "D": 9, "F": 10, "E": "∞",
    }
    assert coluna(resultado, "caminho")["E"] == []
    assert resultado["caminho_destino"]["custo"] == "∞"


def test_direcionado_kruskal_avisa_e_ignora_direcao(direcionado):
    resultado = kruskal(direcionado)
    assert resultado["custo_total"] == 10
    assert len(resultado["arestas_selecionadas"]) == 6
    assert any("não direcionados" in aviso for aviso in resultado["avisos"])


def test_direcionado_kruskal_com_duas_direcoes_escolhe_a_mais_barata():
    grafo = ListaAdjacencia(direcionado=True)
    grafo.adicionar_aresta("A", "B", 9)
    grafo.adicionar_aresta("B", "A", 2)
    resultado = kruskal(grafo)
    assert resultado["custo_total"] == 2
    assert [passo["aceita"] for passo in resultado["passos"]] == [True, False]


# Grafo sem peso


@pytest.fixture
def sem_peso():
    return carregar("grafo_sem_peso")


def test_sem_peso_buscas(sem_peso):
    assert dfs(sem_peso, "A")["ordem_visita"] == ["A", "B", "D", "C", "E"]
    assert bfs(sem_peso, "A")["ordem_visita"] == ["A", "B", "C", "D", "E"]
    assert dfs(sem_peso, "A")["becos_sem_saida"] == ["E"]


def test_sem_peso_dijkstra_equivale_aos_niveis_da_bfs(sem_peso):
    assert distancias(dijkstra(sem_peso, "A")) == coluna(bfs(sem_peso, "A"), "nivel")


def test_sem_peso_kruskal_conta_cada_aresta_como_1(sem_peso):
    resultado = kruskal(sem_peso)
    assert resultado["custo_total"] == 4
    assert any("sem peso" in aviso for aviso in resultado["avisos"])


# Grafo desconexo e vértice isolado


@pytest.fixture
def desconexo():
    return carregar("grafo_desconexo")


def test_desconexo_dfs(desconexo):
    resultado = dfs(desconexo, "A")
    assert resultado["ordem_visita"] == ["A", "B", "C"]
    assert resultado["nao_alcancaveis"] == ["X", "Y", "Z"]
    assert resultado["conectividade"]["conexo"] is False
    assert resultado["conectividade"]["componentes"] == [["A", "B", "C"], ["X", "Y"], ["Z"]]
    assert coluna(resultado, "descoberta")["X"] is None


def test_desconexo_bfs(desconexo):
    resultado = bfs(desconexo, "A")
    assert resultado["ordem_visita"] == ["A", "B", "C"]
    assert coluna(resultado, "nivel")["Z"] is None


def test_desconexo_dijkstra_usa_infinito(desconexo):
    assert distancias(dijkstra(desconexo, "A")) == {
        "A": 0, "B": 1, "C": 3, "X": "∞", "Y": "∞", "Z": "∞",
    }


def test_desconexo_kruskal_devolve_floresta_e_avisa(desconexo):
    resultado = kruskal(desconexo)
    assert resultado["custo_total"] == 6
    assert resultado["floresta"] is True
    assert resultado["componentes"] == 3
    assert len(resultado["arestas_selecionadas"]) == 3
    assert any("floresta" in aviso for aviso in resultado["avisos"])


def test_vertice_isolado_como_origem():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "B", 1)
    grafo.adicionar_vertice("Z")
    assert dfs(grafo, "Z")["ordem_visita"] == ["Z"]
    assert dfs(grafo, "Z")["arvore_texto"] == "Z"
    assert dfs(grafo, "Z")["nao_alcancaveis"] == ["A", "B"]
    assert bfs(grafo, "Z")["ordem_visita"] == ["Z"]
    assert distancias(dijkstra(grafo, "Z")) == {"Z": 0, "A": "∞", "B": "∞"}
    assert kruskal(grafo)["componentes"] == 2


def test_grafo_com_um_unico_vertice():
    grafo = ListaAdjacencia()
    grafo.adicionar_vertice("A")
    assert dfs(grafo, "A")["conectividade"]["conexo"] is True
    assert dfs(grafo, "A")["becos_sem_saida"] == []
    assert kruskal(grafo)["custo_total"] == 0
    assert kruskal(grafo)["floresta"] is False


def test_kruskal_em_grafo_vazio():
    resultado = kruskal(ListaAdjacencia())
    assert resultado["custo_total"] == 0
    assert resultado["arestas_selecionadas"] == []
    assert resultado["floresta"] is False


# Pesos especiais


def test_dijkstra_rejeita_peso_negativo_explicando():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "B", -1)
    with pytest.raises(ErroGrafo, match="pesos negativos"):
        dijkstra(grafo, "A")


def test_kruskal_aceita_peso_negativo():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "B", -3)
    grafo.adicionar_aresta("B", "C", 2)
    grafo.adicionar_aresta("A", "C", 5)
    assert kruskal(grafo)["custo_total"] == -1


def test_pesos_decimais_nao_exibem_ruido_de_ponto_flutuante():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "B", 0.1)
    grafo.adicionar_aresta("B", "C", 0.2)
    assert distancias(dijkstra(grafo, "A"))["C"] == 0.3
    assert kruskal(grafo)["custo_total"] == 0.3


def test_peso_zero():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "B", 0)
    assert distancias(dijkstra(grafo, "A"))["B"] == 0


# Self-loop


def test_self_loop_nao_altera_resultados():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "A", 1)
    grafo.adicionar_aresta("A", "B", 2)
    assert dfs(grafo, "A")["ordem_visita"] == ["A", "B"]
    assert dfs(grafo, "A")["becos_sem_saida"] == ["A", "B"]
    assert bfs(grafo, "A")["ordem_visita"] == ["A", "B"]
    assert distancias(dijkstra(grafo, "A")) == {"A": 0, "B": 2}
    resultado = kruskal(grafo)
    assert resultado["custo_total"] == 2
    assert resultado["passos"][0]["aceita"] is False
    assert any("Self-loop" in aviso for aviso in resultado["avisos"])


# Origem e destino inválidos


@pytest.mark.parametrize("algoritmo", [dfs, bfs, dijkstra])
@pytest.mark.parametrize("origem", ["X", "", None])
def test_origem_invalida(algoritmo, origem):
    grafo = ListaAdjacencia()
    grafo.adicionar_vertice("A")
    with pytest.raises(ErroGrafo):
        algoritmo(grafo, origem)


@pytest.mark.parametrize("algoritmo", [bfs, dijkstra])
def test_destino_invalido(algoritmo):
    grafo = ListaAdjacencia()
    grafo.adicionar_vertice("A")
    with pytest.raises(ErroGrafo, match="destino"):
        algoritmo(grafo, "A", "X")


def test_origem_igual_ao_destino():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "B", 1)
    assert bfs(grafo, "A", "A")["caminho_destino"]["caminho"] == ["A"]
    assert dijkstra(grafo, "A", "A")["caminho_destino"]["custo"] == 0


def test_caminho_longo_nao_estoura_recursao():
    grafo = ListaAdjacencia(direcionado=True, ponderado=False)
    for i in range(3000):
        grafo.adicionar_aresta(i, i + 1)
    resultado = dfs(grafo, "0")
    assert len(resultado["ordem_visita"]) == 3001
    assert resultado["conectividade"]["fracamente_conexo"] is True


# Comparação com soluções de referência em grafos aleatórios


def grafo_aleatorio(gerador, direcionado):
    grafo = ListaAdjacencia(direcionado=direcionado)
    total = gerador.randint(1, 12)
    for i in range(total):
        grafo.adicionar_vertice(f"V{i}")
    for _ in range(gerador.randint(0, total * 3)):
        a, b = f"V{gerador.randrange(total)}", f"V{gerador.randrange(total)}"
        if not grafo.tem_aresta(a, b):
            grafo.adicionar_aresta(a, b, gerador.randint(0, 20))
    return grafo


def bellman_ford(grafo, origem):
    distancia = {v: math.inf for v in grafo.vertices()}
    distancia[origem] = 0
    for _ in grafo.vertices():
        for vertice in grafo.vertices():
            for vizinho, peso in grafo.vizinhos(vertice):
                distancia[vizinho] = min(distancia[vizinho], distancia[vertice] + peso)
    return distancia


def prim_custo(grafo):
    """Custo da floresta geradora mínima por Prim ingênuo, ignorando a direção."""
    arestas = grafo.arestas()
    fora = set(grafo.vertices())
    custo = 0
    while fora:
        dentro = {fora.pop()}
        while True:
            candidatas = [
                (p, a, b) for a, b, p in arestas if (a in dentro) != (b in dentro)
            ]
            if not candidatas:
                break
            peso, a, b = min(candidatas)
            custo += peso
            novo = a if a not in dentro else b
            dentro.add(novo)
            fora.discard(novo)
    return custo


def niveis_por_camadas(grafo, origem):
    niveis = {origem: 0}
    camada = [origem]
    while camada:
        proxima = []
        for vertice in camada:
            for vizinho, _ in grafo.vizinhos(vertice):
                if vizinho not in niveis:
                    niveis[vizinho] = niveis[vertice] + 1
                    proxima.append(vizinho)
        camada = proxima
    return niveis


@pytest.mark.parametrize("semente", range(100))
def test_aleatorio_coincide_com_referencias(semente):
    gerador = random.Random(semente)
    grafo = grafo_aleatorio(gerador, direcionado=semente % 2 == 0)
    origem = gerador.choice(grafo.vertices())

    esperado = {
        v: ("∞" if d == math.inf else d) for v, d in bellman_ford(grafo, origem).items()
    }
    resultado = dijkstra(grafo, origem)
    assert distancias(resultado) == esperado
    for linha in resultado["tabela"]:
        if linha["caminho"]:
            custo = sum(
                dict(grafo.vizinhos(a))[b]
                for a, b in zip(linha["caminho"], linha["caminho"][1:])
            )
            assert custo == linha["distancia"]

    assert kruskal(grafo)["custo_total"] == prim_custo(grafo)

    niveis = niveis_por_camadas(grafo, origem)
    resultado_bfs = bfs(grafo, origem)
    assert {v: n for v, n in coluna(resultado_bfs, "nivel").items() if n is not None} == niveis

    # DFS e BFS alcançam exatamente o mesmo conjunto de vértices, sem repetir.
    ordem = dfs(grafo, origem)["ordem_visita"]
    assert len(ordem) == len(set(ordem))
    assert set(ordem) == set(niveis)
