"""Testes da lista de adjacência e das estruturas auxiliares."""

import random

import pytest

from src.core.grafo import ErroGrafo, ListaAdjacencia
from src.core.heap_minimo import HeapMinimo
from src.core.ordenacao import merge_sort
from src.core.union_find import UnionFind


def nao_direcionado():
    grafo = ListaAdjacencia(direcionado=False, ponderado=True)
    grafo.adicionar_aresta("O", "C", 4)
    grafo.adicionar_aresta("O", "A", 2)
    grafo.adicionar_aresta("B", "O", 5)
    return grafo


def test_nao_direcionado_guarda_nos_dois_sentidos_e_conta_uma_vez():
    grafo = nao_direcionado()
    assert ("O", 2) in grafo.vizinhos("A")
    assert ("A", 2) in grafo.vizinhos("O")
    assert grafo.numero_arestas() == 3


def test_direcionado_guarda_em_um_sentido():
    grafo = ListaAdjacencia(direcionado=True)
    grafo.adicionar_aresta("A", "B", 3)
    assert grafo.vizinhos("A") == [("B", 3)]
    assert grafo.vizinhos("B") == []
    assert not grafo.tem_aresta("B", "A")


def test_vizinhos_e_vertices_em_ordem_alfabetica():
    grafo = nao_direcionado()
    assert grafo.vizinhos("O") == [("A", 2), ("B", 5), ("C", 4)]
    assert grafo.vertices() == ["A", "B", "C", "O"]


def test_ordem_ignora_caixa_e_acento_e_compara_numeros_pelo_valor():
    grafo = ListaAdjacencia(ponderado=False)
    for vertice in ["10", "2", "Centro", "Água", "lapa"]:
        grafo.adicionar_vertice(vertice)
    assert grafo.vertices() == ["2", "10", "Água", "Centro", "lapa"]


def test_nomes_que_diferem_so_na_caixa_sao_vertices_distintos():
    grafo = ListaAdjacencia(ponderado=False)
    grafo.adicionar_aresta("a", "A")
    assert grafo.numero_vertices() == 2
    assert grafo.tem_aresta("A", "a")


def test_aresta_duplicada_e_rejeitada_nos_dois_sentidos():
    grafo = nao_direcionado()
    with pytest.raises(ErroGrafo, match="já existe"):
        grafo.adicionar_aresta("O", "A", 9)
    with pytest.raises(ErroGrafo, match="já existe"):
        grafo.adicionar_aresta("A", "O", 9)
    assert grafo.numero_arestas() == 3


def test_direcionado_aceita_as_duas_direcoes_como_arestas_distintas():
    grafo = ListaAdjacencia(direcionado=True)
    grafo.adicionar_aresta("A", "B", 1)
    grafo.adicionar_aresta("B", "A", 2)
    assert grafo.numero_arestas() == 2
    assert grafo.vizinhos("B") == [("A", 2)]


def test_vertice_duplicado_e_rejeitado():
    grafo = nao_direcionado()
    with pytest.raises(ErroGrafo, match="já existe"):
        grafo.adicionar_vertice("O")


def test_remover_aresta_nos_dois_sentidos():
    grafo = nao_direcionado()
    grafo.remover_aresta("A", "O")
    assert not grafo.tem_aresta("O", "A")
    assert not grafo.tem_aresta("A", "O")
    assert grafo.numero_arestas() == 2


def test_remover_aresta_inexistente_explica_o_erro():
    with pytest.raises(ErroGrafo, match="não existe"):
        nao_direcionado().remover_aresta("A", "B")


def test_remover_vertice_limpa_as_listas_e_o_contador():
    grafo = nao_direcionado()
    grafo.remover_vertice("O")
    assert grafo.vertices() == ["A", "B", "C"]
    assert grafo.vizinhos("A") == []
    assert grafo.numero_arestas() == 0


def test_remover_vertice_direcionado_retira_arestas_de_entrada_e_saida():
    grafo = ListaAdjacencia(direcionado=True)
    grafo.adicionar_aresta("A", "B", 1)
    grafo.adicionar_aresta("B", "C", 1)
    grafo.adicionar_aresta("C", "A", 1)
    grafo.remover_vertice("B")
    assert grafo.vizinhos("A") == []
    assert grafo.vizinhos("C") == [("A", 1)]
    assert grafo.numero_arestas() == 1


def test_alterar_peso_atualiza_os_dois_sentidos():
    grafo = nao_direcionado()
    grafo.alterar_peso("O", "C", 6)
    assert ("C", 6) in grafo.vizinhos("O")
    assert ("O", 6) in grafo.vizinhos("C")


def test_alterar_peso_em_grafo_sem_peso_e_rejeitado():
    grafo = ListaAdjacencia(ponderado=False)
    grafo.adicionar_aresta("A", "B")
    with pytest.raises(ErroGrafo, match="não tem pesos"):
        grafo.alterar_peso("A", "B", 3)


def test_sem_peso_usa_1_internamente_e_esconde_na_exibicao():
    grafo = ListaAdjacencia(ponderado=False)
    grafo.adicionar_aresta("A", "B", 99)
    assert grafo.vizinhos("A") == [("B", 1)]
    assert grafo.para_dict()["A"] == [{"vizinho": "B"}]


@pytest.mark.parametrize("peso", ["2", None, True, float("nan"), float("inf"), 10**400])
def test_peso_invalido_e_rejeitado(peso):
    with pytest.raises(ErroGrafo):
        nao_direcionado().adicionar_aresta("X", "Y", peso)


def test_peso_invalido_nao_deixa_vertices_criados():
    grafo = nao_direcionado()
    with pytest.raises(ErroGrafo):
        grafo.adicionar_aresta("X", "Y", "abc")
    assert not grafo.tem_vertice("X")


@pytest.mark.parametrize("nome", ["", "   ", None, 1.5, True, "x" * 61])
def test_nome_invalido_e_rejeitado(nome):
    with pytest.raises(ErroGrafo):
        ListaAdjacencia().adicionar_vertice(nome)


def test_self_loop_e_aceito_com_aviso_e_contado_uma_vez():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "A", 3)
    assert grafo.vizinhos("A") == [("A", 3)]
    assert grafo.numero_arestas() == 1
    assert "Self-loop em A" in grafo.avisos()[0]
    grafo.remover_aresta("A", "A")
    assert grafo.numero_arestas() == 0
    assert grafo.avisos() == []


def test_remover_vertice_com_self_loop():
    grafo = ListaAdjacencia()
    grafo.adicionar_aresta("A", "A", 3)
    grafo.adicionar_aresta("A", "B", 1)
    grafo.remover_vertice("A")
    assert grafo.numero_arestas() == 0
    assert grafo.avisos() == []


def test_densidade():
    grafo = ListaAdjacencia(ponderado=False)
    assert grafo.densidade() == 0
    grafo.adicionar_aresta("A", "B")
    grafo.adicionar_aresta("B", "C")
    grafo.adicionar_aresta("A", "C")
    assert grafo.densidade() == 1
    direcionado = ListaAdjacencia(direcionado=True, ponderado=False)
    direcionado.adicionar_aresta("A", "B")
    assert direcionado.densidade() == 0.5


def test_ida_e_volta_em_json_preserva_o_grafo():
    for direcionado, ponderado in [(False, True), (True, True), (False, False), (True, False)]:
        grafo = ListaAdjacencia(direcionado=direcionado, ponderado=ponderado)
        grafo.adicionar_aresta("B", "A", 2)
        grafo.adicionar_aresta("B", "C", 3)
        grafo.adicionar_vertice("Z")
        copia = ListaAdjacencia.from_json(grafo.para_json())
        assert copia.para_json() == grafo.para_json()
        assert copia.para_dict() == grafo.para_dict()


def test_from_json_aceita_texto_e_nomes_numericos():
    grafo = ListaAdjacencia.from_json(
        '{"ponderado": false, "vertices": [1, 2], "arestas": [{"origem": 1, "destino": 2}]}'
    )
    assert grafo.vizinhos("1") == [("2", 1)]


@pytest.mark.parametrize(
    "dados",
    [
        "{invalido",
        "[]",
        {"direcionado": "sim"},
        {"vertices": "A"},
        {"arestas": [{"origem": "A"}]},
        {"arestas": [{"origem": "A", "destino": "B"}]},
        {"vertices": ["A", "A"]},
        {"arestas": [
            {"origem": "A", "destino": "B", "peso": 1},
            {"origem": "B", "destino": "A", "peso": 1},
        ]},
    ],
)
def test_from_json_rejeita_entrada_invalida(dados):
    with pytest.raises(ErroGrafo):
        ListaAdjacencia.from_json(dados)


def test_consultar_vertice_inexistente_explica_o_erro():
    with pytest.raises(ErroGrafo, match="não existe"):
        ListaAdjacencia().vizinhos("X")


# Estruturas auxiliares


def test_merge_sort_coincide_com_sorted():
    gerador = random.Random(1)
    for tamanho in [0, 1, 2, 3, 10, 257]:
        dados = [gerador.randint(-50, 50) for _ in range(tamanho)]
        original = list(dados)
        assert merge_sort(dados) == sorted(dados)
        assert dados == original


def test_merge_sort_e_estavel():
    dados = [(2, "a"), (1, "b"), (2, "c"), (1, "d")]
    assert merge_sort(dados, chave=lambda item: item[0]) == [
        (1, "b"), (1, "d"), (2, "a"), (2, "c"),
    ]


def test_heap_extrai_em_ordem_crescente():
    gerador = random.Random(2)
    dados = [gerador.randint(-100, 100) for _ in range(300)]
    heap = HeapMinimo()
    for item in dados:
        heap.inserir(item)
    assert len(heap) == 300
    assert heap.minimo() == min(dados)
    assert [heap.extrair_minimo() for _ in range(300)] == sorted(dados)
    assert heap.esta_vazio()


def test_heap_vazio_avisa():
    with pytest.raises(IndexError):
        HeapMinimo().extrair_minimo()


def test_union_find_une_e_detecta_ciclo():
    conjuntos = UnionFind("ABCD")
    assert conjuntos.total_conjuntos == 4
    assert conjuntos.unir("A", "B")
    assert conjuntos.unir("C", "D")
    assert conjuntos.encontrar("A") != conjuntos.encontrar("C")
    assert conjuntos.unir("B", "D")
    assert not conjuntos.unir("A", "C")
    assert conjuntos.total_conjuntos == 1
    assert len({conjuntos.encontrar(x) for x in "ABCD"}) == 1
