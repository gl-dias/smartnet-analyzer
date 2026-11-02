"""Testes das rotas de estrutura e de algoritmos."""

import pytest
from fastapi.testclient import TestClient

from src.app import app

cliente = TestClient(app)


def exemplo(nome="grafo_enunciado"):
    return cliente.get(f"/api/exemplos/{nome}").json()


def test_saude():
    assert cliente.get("/saude").json() == {"status": "ok"}


def test_pagina_principal_e_estaticos():
    assert "SmartNet" in cliente.get("/").text
    for caminho in ["/css/estilos.css", "/js/app.js", "/js/grafo_visual.js"]:
        assert cliente.get(caminho).status_code == 200


def test_estrutura_devolve_lista_e_estatisticas():
    corpo = cliente.post("/api/estrutura", json=exemplo()).json()
    assert corpo["estatisticas"] == {"vertices": 8, "arestas": 14, "densidade": 0.5}
    primeiro = corpo["lista_adjacencia"][0]
    assert primeiro["vertice"] == "A"
    assert primeiro["vizinhos"][0] == {"vizinho": "B", "peso": 2}


def test_estrutura_sem_peso_esconde_o_peso():
    corpo = cliente.post("/api/estrutura", json=exemplo("grafo_sem_peso")).json()
    assert corpo["lista_adjacencia"][0]["vizinhos"][0] == {"vizinho": "B"}


def test_vertices_numericos_mantem_a_ordem_em_lista():
    grafo = {"ponderado": False, "vertices": ["10", "2", "x"]}
    corpo = cliente.post("/api/estrutura", json=grafo).json()
    assert [item["vertice"] for item in corpo["lista_adjacencia"]] == ["2", "10", "x"]


def test_grafo_vazio_e_aceito():
    corpo = cliente.post("/api/estrutura", json={}).json()
    assert corpo["estatisticas"]["vertices"] == 0


def test_aresta_duplicada_devolve_mensagem_em_portugues():
    grafo = {"arestas": [
        {"origem": "A", "destino": "B", "peso": 1},
        {"origem": "B", "destino": "A", "peso": 2},
    ]}
    resposta = cliente.post("/api/estrutura", json=grafo)
    assert resposta.status_code == 422
    assert "já existe" in resposta.json()["erro"]


@pytest.mark.parametrize(
    "grafo, trecho",
    [
        ({"arestas": [{"origem": "A"}]}, "arestas.0.destino: campo obrigatório"),
        ({"arestas": [{"origem": "A", "destino": "B", "peso": "x"}]}, "arestas.0.peso"),
        ({"direcionado": "sim"}, "direcionado: deve ser verdadeiro ou falso"),
        ({"vertices": "A"}, "vertices: deve ser uma lista"),
        ({"arestas": [{"origem": "A", "destino": "B"}]}, "está sem peso"),
    ],
)
def test_validacao_em_portugues(grafo, trecho):
    resposta = cliente.post("/api/estrutura", json=grafo)
    assert resposta.status_code == 422
    assert trecho in resposta.json()["erro"]


def test_json_malformado():
    resposta = cliente.post(
        "/api/estrutura", content="{", headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 422
    assert "JSON inválido" in resposta.json()["erro"]


@pytest.mark.parametrize(
    "algoritmo, verificar",
    [
        ("dfs", lambda r: r["ordem_visita"] == ["O", "A", "B", "C", "E", "D", "T", "F"]),
        ("bfs", lambda r: r["ordem_visita"] == ["O", "A", "B", "C", "D", "F", "E", "T"]),
        ("dijkstra", lambda r: {l["vertice"]: l["distancia"] for l in r["tabela"]}
            == {"O": 0, "A": 2, "B": 4, "C": 4, "E": 7, "D": 8, "T": 13, "F": 14}),
        ("kruskal", lambda r: r["custo_total"] == 20),
    ],
)
def test_algoritmos_no_grafo_do_enunciado(algoritmo, verificar):
    resposta = cliente.post(
        f"/api/algoritmos/{algoritmo}", json={"grafo": exemplo(), "origem": "O"}
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert verificar(corpo)
    assert corpo["tempo_ms"] >= 0
    assert corpo["complexidade"]["tempo"].startswith("O(")


def test_destino_vazio_e_tratado_como_ausente():
    corpo = cliente.post(
        "/api/algoritmos/bfs", json={"grafo": exemplo(), "origem": "O", "destino": ""}
    ).json()
    assert corpo["caminho_destino"] is None


def test_destino_e_usado():
    corpo = cliente.post(
        "/api/algoritmos/dijkstra", json={"grafo": exemplo(), "origem": "O", "destino": "T"}
    ).json()
    assert corpo["caminho_destino"]["custo"] == 13


def test_infinito_chega_como_texto_no_json():
    corpo = cliente.post(
        "/api/algoritmos/dijkstra", json={"grafo": exemplo("grafo_desconexo"), "origem": "A"}
    ).json()
    assert {l["vertice"]: l["distancia"] for l in corpo["tabela"]}["Z"] == "∞"


def test_kruskal_nao_exige_origem():
    corpo = cliente.post("/api/algoritmos/kruskal", json={"grafo": exemplo()}).json()
    assert corpo["custo_total"] == 20


def test_algoritmo_desconhecido():
    resposta = cliente.post("/api/algoritmos/prim", json={"grafo": exemplo()})
    assert resposta.status_code == 404
    assert "prim" in resposta.json()["erro"]


def test_dijkstra_com_peso_negativo_explica_o_motivo():
    grafo = {"arestas": [{"origem": "A", "destino": "B", "peso": -1}]}
    resposta = cliente.post("/api/algoritmos/dijkstra", json={"grafo": grafo, "origem": "A"})
    assert resposta.status_code == 422
    assert "pesos negativos" in resposta.json()["erro"]


def test_origem_inexistente():
    resposta = cliente.post("/api/algoritmos/dfs", json={"grafo": exemplo(), "origem": "Z"})
    assert resposta.status_code == 422
    assert "não existe" in resposta.json()["erro"]


def test_todos_os_exemplos_rodam_em_todos_os_algoritmos():
    for nome in ["grafo_enunciado", "grafo_direcionado", "grafo_sem_peso", "grafo_desconexo"]:
        grafo = exemplo(nome)
        origem = grafo["vertices"][0]
        for algoritmo in ["dfs", "bfs", "dijkstra", "kruskal"]:
            resposta = cliente.post(
                f"/api/algoritmos/{algoritmo}", json={"grafo": grafo, "origem": origem}
            )
            assert resposta.status_code == 200, (nome, algoritmo, resposta.text)


def test_exemplo_desconhecido_nao_le_outros_arquivos():
    assert cliente.get("/api/exemplos/segredo").status_code == 404
    assert cliente.get("/api/exemplos/..%2F..%2F.env").status_code == 404


def test_rota_inexistente_em_portugues():
    assert cliente.get("/api/nada").json() == {"erro": "Recurso não encontrado."}


def test_finalizar_sessao():
    assert cliente.post("/api/sessao/finalizar", json={}).json() == {"ok": True}
