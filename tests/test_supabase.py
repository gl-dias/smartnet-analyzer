"""Testes do acesso ao banco, sobre um servidor HTTP simulado: nenhum toca no Supabase de verdade."""

import json
import logging
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from src import config
from src.app import app
from src.db import supabase_rest
from src.ia import interpretador
from tests.conftest import SENHA_TESTE, USUARIO_TESTE
from tests.test_ia import ADICIONAR_T, ClienteFalso, bloco_ferramenta, resposta_modelo

CHAVE_NOVA = "sb_secret_chave-de-teste"
CHAVE_ANTIGA = "eyJchave.de.teste"
GRAFO = {
    "direcionado": False,
    "ponderado": True,
    "vertices": ["O", "A"],
    "arestas": [{"origem": "O", "destino": "A", "peso": 2}],
}
ID = str(uuid.uuid4())


class Banco:
    """Servidor falso: registra as requisições e responde conforme configurado."""

    def __init__(self):
        self.requisicoes = []
        self.respostas = {}
        self.falha = None

    def __call__(self, requisicao):
        self.requisicoes.append(requisicao)
        if isinstance(self.falha, Exception):
            raise self.falha
        if self.falha:
            return httpx.Response(self.falha, json={"code": "XX", "message": "falha"})
        tabela = requisicao.url.path.rsplit("/", 1)[-1]
        conteudo = self.respostas.get((requisicao.method, tabela))
        if conteudo is None:
            return httpx.Response(201 if requisicao.method == "POST" else 204)
        return httpx.Response(200, json=conteudo)

    def de(self, metodo, tabela):
        return [
            r for r in self.requisicoes
            if r.method == metodo and r.url.path == f"/rest/v1/{tabela}"
        ]

    def corpo(self, metodo, tabela):
        return json.loads(self.de(metodo, tabela)[-1].content)


@pytest.fixture
def banco(monkeypatch):
    falso = Banco()
    monkeypatch.setattr(config, "SUPABASE_URL", "https://projeto.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", CHAVE_NOVA)
    monkeypatch.setattr(
        supabase_rest, "_criar_cliente", lambda: httpx.Client(transport=httpx.MockTransport(falso))
    )
    return falso


def logar():
    cliente = TestClient(app)
    resposta = cliente.post("/login", json={"usuario": USUARIO_TESTE, "senha": SENHA_TESTE})
    assert resposta.status_code == 200
    return cliente


def salvar(cliente, **campos):
    corpo = {"nome": "Minha cidade", "grafo": GRAFO, "origem_entrada": "manual", **campos}
    return cliente.post("/api/grafos", json=corpo)


# Formato da chave


@pytest.mark.parametrize(
    "chave, espera_authorization", [(CHAVE_NOVA, False), (CHAVE_ANTIGA, True)]
)
def test_cabecalhos_seguem_o_formato_da_chave(banco, monkeypatch, chave, espera_authorization):
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", chave)
    banco.respostas[("GET", "grafos")] = []
    supabase_rest.listar_grafos()
    cabecalhos = banco.requisicoes[0].headers
    assert cabecalhos["apikey"] == chave
    if espera_authorization:
        assert cabecalhos["authorization"] == f"Bearer {chave}"
    else:
        assert "authorization" not in cabecalhos


def test_url_com_barra_no_final_funciona(banco, monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://projeto.supabase.co/")
    banco.respostas[("GET", "grafos")] = []
    supabase_rest.listar_grafos()
    assert banco.requisicoes[0].url.path == "/rest/v1/grafos"


# Grafos


def test_salvar_grafo_grava_os_campos_e_a_sessao(banco):
    banco.respostas[("POST", "grafos")] = [{"id": ID, "nome": "Minha cidade", "criado_em": "agora"}]
    cliente = logar()
    resposta = salvar(cliente, nome="  Minha cidade  ", origem_entrada="voz")
    assert resposta.status_code == 201
    assert resposta.json()["id"] == ID
    corpo = banco.corpo("POST", "grafos")
    assert corpo["nome"] == "Minha cidade"
    assert corpo["origem_entrada"] == "voz"
    assert corpo["direcionado"] is False
    assert sorted(corpo["vertices"]) == ["A", "O"]
    assert corpo["arestas"] == GRAFO["arestas"]
    assert uuid.UUID(corpo["sessao_id"])
    sessoes = [json.loads(r.content)["id"] for r in banco.de("POST", "sessoes")]
    assert corpo["sessao_id"] in sessoes


def test_sessao_e_registrada_antes_do_grafo_e_sem_duplicar(banco):
    banco.respostas[("POST", "grafos")] = [{"id": ID, "nome": "x", "criado_em": "agora"}]
    salvar(logar())
    caminhos = [r.url.path.rsplit("/", 1)[-1] for r in banco.requisicoes]
    assert caminhos == ["sessoes", "sessoes", "grafos"]
    registro = banco.de("POST", "sessoes")[-1]
    assert "ignore-duplicates" in registro.headers["prefer"]
    assert registro.url.params["on_conflict"] == "id"


def test_salvar_preserva_sentido_e_peso_oculto(banco):
    banco.respostas[("POST", "grafos")] = [{"id": ID, "nome": "x", "criado_em": "agora"}]
    grafo = {"ponderado": False, "vertices": [], "arestas": [{"origem": "Z", "destino": "A", "peso": 7}]}
    assert salvar(logar(), grafo=grafo).status_code == 201
    corpo = banco.corpo("POST", "grafos")
    assert corpo["arestas"] == [{"origem": "Z", "destino": "A", "peso": 7}]
    assert corpo["vertices"] == ["A", "Z"]


@pytest.mark.parametrize(
    "campos, trecho",
    [
        ({"nome": "   "}, "nome"),
        ({"nome": "x" * 101}, "100"),
        ({"grafo": {"vertices": []}}, "vazio"),
        ({"grafo": {"vertices": ["A", "A"]}}, "já existe"),
        ({"origem_entrada": "telepatia"}, "valor não permitido"),
    ],
)
def test_salvar_invalido_nao_chega_ao_banco(banco, campos, trecho):
    cliente = logar()
    quantidade = len(banco.requisicoes)
    resposta = salvar(cliente, **campos)
    assert resposta.status_code == 422
    assert trecho in resposta.json()["erro"]
    assert len(banco.requisicoes) == quantidade


def test_listar_grafos_ordena_e_limita(banco):
    banco.respostas[("GET", "grafos")] = [{"id": ID, "nome": "x"}]
    corpo = logar().get("/api/grafos").json()
    assert corpo == {"grafos": [{"id": ID, "nome": "x"}]}
    parametros = banco.de("GET", "grafos")[0].url.params
    assert parametros["order"] == "criado_em.desc"
    assert parametros["limit"] == "100"
    assert "vertices" not in parametros["select"]


def test_carregar_grafo_salvo(banco):
    banco.respostas[("GET", "grafos")] = [{**GRAFO, "id": ID, "nome": "x", "origem_entrada": "texto"}]
    resposta = logar().get(f"/api/grafos/{ID}")
    assert resposta.status_code == 200
    assert resposta.json()["origem_entrada"] == "texto"
    assert banco.de("GET", "grafos")[0].url.params["id"] == f"eq.{ID}"


def test_grafo_salvo_carregado_e_aceito_pela_estrutura(banco):
    banco.respostas[("GET", "grafos")] = [{**GRAFO, "id": ID, "nome": "x", "origem_entrada": "texto", "criado_em": "agora"}]
    cliente = logar()
    linha = cliente.get(f"/api/grafos/{ID}").json()
    assert cliente.post("/api/estrutura", json=linha).status_code == 200


def test_carregar_grafo_inexistente(banco):
    banco.respostas[("GET", "grafos")] = []
    resposta = logar().get(f"/api/grafos/{ID}")
    assert resposta.status_code == 404
    assert "não encontrado" in resposta.json()["erro"]


def test_apagar_grafo(banco):
    banco.respostas[("DELETE", "grafos")] = [{"id": ID}]
    assert logar().delete(f"/api/grafos/{ID}").json() == {"ok": True}
    assert banco.de("DELETE", "grafos")[0].url.params["id"] == f"eq.{ID}"


def test_apagar_grafo_inexistente(banco):
    banco.respostas[("DELETE", "grafos")] = []
    assert logar().delete(f"/api/grafos/{ID}").status_code == 404


@pytest.mark.parametrize("identificador", ["abc", "1%20or%201=1", "neq.0"])
def test_identificador_invalido_nao_chega_ao_banco(banco, identificador):
    cliente = logar()
    quantidade = len(banco.requisicoes)
    assert cliente.delete(f"/api/grafos/{identificador}").status_code == 422
    assert cliente.get(f"/api/grafos/{identificador}").status_code == 422
    assert len(banco.requisicoes) == quantidade


# Sessão


def test_login_registra_sessao_e_finalizar_marca_o_fim(banco):
    cliente = logar()
    sessao_id = banco.corpo("POST", "sessoes")["id"]
    assert cliente.post("/api/sessao/finalizar").json() == {"ok": True}
    atualizacao = banco.de("PATCH", "sessoes")[0]
    assert atualizacao.url.params["id"] == f"eq.{sessao_id}"
    assert "finalizada_em" in json.loads(atualizacao.content)
    assert cliente.get("/api/grafos").status_code == 401


def test_logout_tambem_marca_o_fim(banco):
    logar().post("/logout")
    assert len(banco.de("PATCH", "sessoes")) == 1


def test_logout_sem_sessao_nao_chama_o_banco(banco):
    TestClient(app).post("/logout")
    assert banco.requisicoes == []


# Execuções


def test_execucao_e_registrada_sem_a_complexidade(banco):
    cliente = logar()
    resposta = cliente.post("/api/algoritmos/dijkstra", json={"grafo": GRAFO, "origem": "O", "grafo_id": ID})
    assert resposta.status_code == 200
    corpo = banco.corpo("POST", "execucoes")
    assert corpo["grafo_id"] == ID
    assert corpo["algoritmo"] == "dijkstra"
    assert corpo["parametros"] == {"origem": "O", "destino": None}
    assert corpo["tempo_ms"] == resposta.json()["tempo_ms"]
    assert corpo["resultado"]["tabela"][0]["vertice"] == "O"
    assert "complexidade" not in corpo["resultado"]


def test_execucao_de_grafo_nao_salvo_fica_sem_grafo_id(banco):
    logar().post("/api/algoritmos/kruskal", json={"grafo": GRAFO})
    assert banco.corpo("POST", "execucoes")["grafo_id"] is None


def test_execucao_que_falha_nao_e_registrada(banco):
    logar().post("/api/algoritmos/dfs", json={"grafo": GRAFO, "origem": "Z"})
    assert banco.de("POST", "execucoes") == []


# Auditoria da IA


@pytest.fixture
def ia(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "chave-falsa")
    monkeypatch.setattr(config, "ANTHROPIC_MODEL", "claude-sonnet-5-5")

    def configurar(resultado):
        monkeypatch.setattr(interpretador, "_criar_cliente", lambda: ClienteFalso(resultado))

    return configurar


def interpretar(cliente, texto="adicione T"):
    return cliente.post("/api/interpretar", json={"texto": texto, "canal": "voz", "grafo": GRAFO})


def test_interpretacao_com_operacoes_e_auditada(banco, ia):
    ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    corpo = interpretar(logar()).json()
    registro = banco.corpo("POST", "interpretacoes_ia")
    assert registro["id"] == corpo["interpretacao_id"]
    assert registro["texto_entrada"] == "adicione T"
    assert registro["canal"] == "voz"
    assert registro["operacoes"][0]["descricao"] == "+ bairro T"
    assert "aceito" not in registro


def test_pergunta_tambem_e_auditada(banco, ia):
    ia(resposta_modelo(bloco_ferramenta(pergunta="Qual o custo?")))
    interpretar(logar())
    assert banco.corpo("POST", "interpretacoes_ia")["operacoes"] == {"pergunta": "Qual o custo?"}


def test_falha_da_ia_tambem_e_auditada(banco, ia):
    ia(resposta_modelo(stop_reason="refusal"))
    resposta = interpretar(logar())
    assert resposta.status_code == 503
    assert "erro" in banco.corpo("POST", "interpretacoes_ia")["operacoes"]


def test_texto_rejeitado_antes_da_ia_nao_e_auditado(banco, ia):
    ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    interpretar(logar(), "x" * 2001)
    assert banco.de("POST", "interpretacoes_ia") == []


@pytest.mark.parametrize("aceito", [True, False])
def test_decisao_da_revisao_e_registrada(banco, aceito):
    resposta = logar().post(f"/api/interpretacoes/{ID}/decisao", json={"aceito": aceito})
    assert resposta.json() == {"ok": True}
    atualizacao = banco.de("PATCH", "interpretacoes_ia")[0]
    assert atualizacao.url.params["id"] == f"eq.{ID}"
    assert json.loads(atualizacao.content) == {"aceito": aceito}


def test_interpretacao_e_uma_previa_nao_grava_o_grafo(banco, ia):
    ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    interpretar(logar())
    assert banco.de("POST", "grafos") == []


# Banco fora do ar


FALHAS = [
    401,
    404,
    500,
    503,
    httpx.ConnectError("sem rede"),
    httpx.ReadTimeout("demorou"),
]


@pytest.mark.parametrize("falha", FALHAS)
def test_rotas_de_grafos_avisam_quando_o_banco_falha(banco, falha):
    cliente = logar()
    banco.falha = falha
    for resposta in [
        cliente.get("/api/grafos"),
        cliente.get(f"/api/grafos/{ID}"),
        cliente.delete(f"/api/grafos/{ID}"),
        salvar(cliente),
    ]:
        assert resposta.status_code == 503
        assert "Exportar JSON" in resposta.json()["erro"]


@pytest.mark.parametrize("falha", FALHAS)
def test_banco_fora_do_ar_nao_afeta_o_restante(banco, ia, falha):
    banco.falha = falha
    ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    cliente = logar()
    assert cliente.post("/api/estrutura", json=GRAFO).status_code == 200
    assert cliente.post("/api/algoritmos/kruskal", json={"grafo": GRAFO}).status_code == 200
    assert interpretar(cliente).status_code == 200
    assert cliente.post(f"/api/interpretacoes/{ID}/decisao", json={"aceito": True}).status_code == 200
    assert cliente.post("/api/sessao/finalizar").status_code == 200


def test_sem_configuracao_o_banco_avisa_e_nada_e_chamado(monkeypatch):
    def nao_deve_chamar():
        raise AssertionError("não deveria abrir conexão")

    monkeypatch.setattr(supabase_rest, "_criar_cliente", nao_deve_chamar)
    cliente = logar()
    assert cliente.get("/api/grafos").status_code == 503
    assert salvar(cliente).status_code == 503
    assert cliente.post("/api/algoritmos/kruskal", json={"grafo": GRAFO}).status_code == 200
    assert cliente.post("/api/sessao/finalizar").status_code == 200


def test_log_e_resposta_nao_expoem_a_chave(banco, caplog):
    cliente = logar()
    banco.falha = 500
    with caplog.at_level(logging.DEBUG):
        resposta = cliente.get("/api/grafos")
    assert CHAVE_NOVA not in caplog.text
    assert CHAVE_NOVA not in resposta.text
    assert "projeto.supabase.co" not in resposta.text


# Proteção


@pytest.mark.parametrize(
    "metodo, caminho",
    [
        ("GET", "/api/grafos"),
        ("POST", "/api/grafos"),
        ("GET", f"/api/grafos/{ID}"),
        ("DELETE", f"/api/grafos/{ID}"),
        ("POST", f"/api/interpretacoes/{ID}/decisao"),
    ],
)
def test_rotas_novas_exigem_sessao(banco, metodo, caminho):
    assert TestClient(app).request(metodo, caminho, json={}).status_code == 401
    assert banco.requisicoes == []
