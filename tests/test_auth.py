"""Testes do login, da proteção de rotas e dos limites de tentativas."""

import logging
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from scripts.gerar_hash_senha import gerar_hash
from src import config
from src.app import app
from src.auth import sessao
from src.auth.rate_limit import LimitadorTaxa, ip_cliente
from tests.conftest import SENHA_TESTE, USUARIO_TESTE

import bcrypt

GRAFO = {"arestas": [{"origem": "A", "destino": "B", "peso": 1}]}


def novo_cliente():
    return TestClient(app, follow_redirects=False)


def entrar(cliente, usuario=USUARIO_TESTE, senha=SENHA_TESTE, cabecalhos=None):
    return cliente.post("/login", json={"usuario": usuario, "senha": senha}, headers=cabecalhos)


@pytest.fixture
def logado():
    cliente = novo_cliente()
    assert entrar(cliente).status_code == 200
    return cliente


# Rotas protegidas sem sessão


@pytest.mark.parametrize(
    "metodo, caminho",
    [
        ("POST", "/api/estrutura"),
        ("POST", "/api/algoritmos/dfs"),
        ("POST", "/api/algoritmos/kruskal"),
        ("GET", "/api/exemplos/grafo_enunciado"),
        ("POST", "/api/sessao/finalizar"),
        ("GET", "/api/rota-que-nao-existe"),
    ],
)
def test_api_sem_sessao_devolve_401(metodo, caminho):
    resposta = novo_cliente().request(metodo, caminho, json=GRAFO)
    assert resposta.status_code == 401
    assert "login" in resposta.json()["erro"]


def test_exemplo_sem_sessao_nao_devolve_o_grafo():
    resposta = novo_cliente().get("/api/exemplos/grafo_enunciado")
    assert "arestas" not in resposta.text


def test_pagina_principal_sem_sessao_redireciona():
    resposta = novo_cliente().get("/")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


@pytest.mark.parametrize("caminho", ["/js/app.js", "/js/grafo_visual.js", "/docs", "/openapi.json"])
def test_demais_arquivos_sem_sessao_sao_bloqueados(caminho):
    assert novo_cliente().get(caminho).status_code == 401


@pytest.mark.parametrize("caminho", ["/login", "/saude", "/css/estilos.css", "/js/login.js"])
def test_caminhos_publicos(caminho):
    assert novo_cliente().get(caminho).status_code == 200


# Login


@pytest.mark.parametrize(
    "usuario, senha",
    [
        (USUARIO_TESTE, "senha-errada"),
        ("outra-pessoa", SENHA_TESTE),
        ("", ""),
        (USUARIO_TESTE, "x" * 200),
    ],
)
def test_login_invalido_usa_mensagem_generica(usuario, senha):
    cliente = novo_cliente()
    resposta = entrar(cliente, usuario, senha)
    assert resposta.status_code == 401
    assert resposta.json() == {"erro": "Usuário ou senha inválidos"}
    assert cliente.post("/api/estrutura", json=GRAFO).status_code == 401


@pytest.mark.parametrize(
    "corpo",
    ['{"usuario": "\\ud800", "senha": "x"}', '{"usuario": "avaliador", "senha": "\\ud800"}'],
)
def test_caractere_invalido_no_login_nao_derruba_o_servidor(corpo):
    resposta = novo_cliente().post(
        "/login", content=corpo, headers={"Content-Type": "application/json"}
    )
    assert resposta.status_code == 401


def test_login_valido_libera_a_api_e_a_pagina(logado):
    assert logado.post("/api/estrutura", json=GRAFO).status_code == 200
    assert logado.get("/api/exemplos/grafo_enunciado").status_code == 200
    assert logado.get("/js/app.js").status_code == 200
    assert "SmartNet" in logado.get("/").text


def test_login_com_sessao_ativa_redireciona_para_a_aplicacao(logado):
    resposta = logado.get("/login")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_cookie_e_httponly_e_samesite_lax_e_dura_8_horas():
    cookie = entrar(novo_cliente()).headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=28800" in cookie


def test_cookie_e_secure_somente_em_producao():
    assert sessao.opcoes_cookie("producao")["https_only"] is True
    assert sessao.opcoes_cookie("local")["https_only"] is False


def test_producao_nao_sobe_sem_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        sessao.chave_secreta("producao", "")
    assert sessao.chave_secreta("producao", "abc") == "abc"
    assert sessao.chave_secreta("local", "")


@pytest.mark.parametrize("valor", ["", "nao-e-um-hash"])
def test_hash_ausente_ou_invalido_nega_o_acesso(monkeypatch, valor):
    monkeypatch.setattr(config, "APP_SENHA_HASH", valor)
    assert entrar(novo_cliente()).status_code == 401


def test_conta_nao_configurada_nega_o_acesso(monkeypatch):
    monkeypatch.setattr(config, "APP_USUARIO", "")
    assert entrar(novo_cliente(), usuario="").status_code == 401


# Sessão


def test_cookie_adulterado_e_recusado(logado):
    valor = logado.cookies["smartnet_sessao"]
    cliente = novo_cliente()
    cliente.cookies.set("smartnet_sessao", valor[:-2] + "xx")
    assert cliente.post("/api/estrutura", json=GRAFO).status_code == 401


def test_cookie_assinado_com_outra_chave_e_recusado():
    import base64
    import json

    conteudo = base64.b64encode(json.dumps({"usuario": USUARIO_TESTE, "inicio": 9e12}).encode())
    forjado = TimestampSigner("outra-chave").sign(conteudo).decode()
    cliente = novo_cliente()
    cliente.cookies.set("smartnet_sessao", forjado)
    assert cliente.post("/api/estrutura", json=GRAFO).status_code == 401


def test_sessao_expira_8_horas_apos_o_login(logado, monkeypatch):
    assert logado.post("/api/estrutura", json=GRAFO).status_code == 200
    agora = sessao._agora()
    monkeypatch.setattr(sessao, "_agora", lambda: agora + 8 * 3600 + 1)
    assert logado.post("/api/estrutura", json=GRAFO).status_code == 401


def test_logout_encerra_a_sessao(logado):
    assert logado.post("/logout").status_code == 200
    assert logado.post("/api/estrutura", json=GRAFO).status_code == 401


def test_finalizar_encerra_a_sessao(logado):
    assert logado.post("/api/sessao/finalizar").json() == {"ok": True}
    assert logado.post("/api/estrutura", json=GRAFO).status_code == 401
    assert logado.get("/").status_code == 303


def test_ambiente_com_erro_de_digitacao_impede_a_subida():
    ambiente = {**os.environ, "AMBIENTE": "production"}
    processo = subprocess.run(
        [sys.executable, "-c", "import src.config"], env=ambiente, capture_output=True, text=True
    )
    assert processo.returncode != 0
    assert "AMBIENTE" in processo.stderr


def test_login_recusado_registra_o_ip_e_nunca_a_senha(monkeypatch, caplog):
    monkeypatch.setattr(config, "AMBIENTE", "producao")
    cabecalho = {"X-Forwarded-For": "10.0.0.1, 203.0.113.9"}
    with caplog.at_level(logging.WARNING, logger="src.auth.sessao"):
        entrar(novo_cliente(), senha="senha-que-nao-pode-vazar", cabecalhos=cabecalho)
    assert "ip=203.0.113.9 x_forwarded_for=10.0.0.1, 203.0.113.9" in caplog.text
    assert "senha-que-nao-pode-vazar" not in caplog.text


def test_conta_ausente_gera_aviso_no_log(monkeypatch, caplog):
    monkeypatch.setattr(config, "APP_SENHA_HASH", "")
    with caplog.at_level(logging.WARNING, logger="src.auth.sessao"):
        sessao.avisar_conta_ausente()
    assert "ninguém conseguirá entrar" in caplog.text


# Limite de tentativas


def test_bloqueia_apos_5_tentativas_mesmo_com_a_senha_certa():
    cliente = novo_cliente()
    for _ in range(5):
        assert entrar(cliente, senha="errada").status_code == 401
    resposta = entrar(cliente)
    assert resposta.status_code == 429
    assert resposta.json() == {"erro": "Muitas tentativas, aguarde alguns minutos"}
    assert cliente.post("/api/estrutura", json=GRAFO).status_code == 401


def test_login_valido_zera_as_tentativas():
    cliente = novo_cliente()
    for _ in range(4):
        entrar(cliente, senha="errada")
    assert entrar(cliente).status_code == 200
    for _ in range(4):
        assert entrar(cliente, senha="errada").status_code == 401


def test_bloqueio_nao_derruba_sessao_ja_aberta(logado):
    outro = novo_cliente()
    for _ in range(6):
        entrar(outro, senha="errada")
    assert logado.post("/api/estrutura", json=GRAFO).status_code == 200


def test_x_forwarded_for_e_ignorado_fora_de_producao():
    cliente = novo_cliente()
    for i in range(5):
        entrar(cliente, senha="errada", cabecalhos={"X-Forwarded-For": f"10.0.0.{i}"})
    assert entrar(cliente, cabecalhos={"X-Forwarded-For": "10.0.1.1"}).status_code == 429


def test_em_producao_cada_ip_tem_sua_contagem(monkeypatch):
    monkeypatch.setattr(config, "AMBIENTE", "producao")
    cliente = novo_cliente()
    primeiro = {"X-Forwarded-For": "203.0.113.1"}
    for _ in range(5):
        assert entrar(cliente, senha="errada", cabecalhos=primeiro).status_code == 401
    assert entrar(cliente, cabecalhos=primeiro).status_code == 429
    assert entrar(cliente, cabecalhos={"X-Forwarded-For": "203.0.113.2"}).status_code == 200


def test_falsificar_o_inicio_da_lista_nao_escapa_do_limite(monkeypatch):
    monkeypatch.setattr(config, "AMBIENTE", "producao")
    cliente = novo_cliente()
    for i in range(5):
        cabecalho = {"X-Forwarded-For": f"10.9.9.{i}, 203.0.113.1"}
        assert entrar(cliente, senha="errada", cabecalhos=cabecalho).status_code == 401
    cabecalho = {"X-Forwarded-For": "10.9.9.200, 203.0.113.1"}
    assert entrar(cliente, cabecalhos=cabecalho).status_code == 429


@pytest.mark.parametrize(
    "proxies, cabecalho, esperado",
    [
        (1, "1.1.1.1, 2.2.2.2, 3.3.3.3", "3.3.3.3"),
        (2, "1.1.1.1, 2.2.2.2, 3.3.3.3", "2.2.2.2"),
        (2, "3.3.3.3", "192.0.2.7"),
        # Formato real no Render: cliente, Cloudflare e proxy interno, às vezes sem espaço.
        (3, "198.51.100.7, 172.71.0.1, 10.24.0.1", "198.51.100.7"),
        (3, "1.2.3.4,198.51.100.7, 172.71.0.1, 10.24.0.1", "198.51.100.7"),
        (0, "1.1.1.1", "192.0.2.7"),
        (1, "", "192.0.2.7"),
    ],
)
def test_proxies_confiaveis_define_qual_ip_usar(monkeypatch, proxies, cabecalho, esperado):
    monkeypatch.setattr(config, "AMBIENTE", "producao")
    monkeypatch.setattr(config, "PROXIES_CONFIAVEIS", proxies)

    class Conexao:
        host = "192.0.2.7"

    class Pedido:
        headers = {"x-forwarded-for": cabecalho}
        client = Conexao()

    assert ip_cliente(Pedido()) == esperado


def test_trocar_de_ip_a_cada_tentativa_esbarra_no_teto_global(monkeypatch):
    monkeypatch.setattr(config, "AMBIENTE", "producao")
    cliente = novo_cliente()
    for i in range(50):
        cabecalho = {"X-Forwarded-For": f"198.51.100.{i}"}
        assert entrar(cliente, senha="errada", cabecalhos=cabecalho).status_code == 401
    assert entrar(cliente, cabecalhos={"X-Forwarded-For": "198.51.100.99"}).status_code == 429


def test_ip_cliente_sem_cabecalho_usa_a_conexao(monkeypatch):
    monkeypatch.setattr(config, "AMBIENTE", "producao")

    class Conexao:
        host = "192.0.2.7"

    class Pedido:
        headers = {}
        client = Conexao()

    assert ip_cliente(Pedido()) == "192.0.2.7"


def test_limitador_libera_quando_a_janela_passa():
    instante = [0.0]
    limitador = LimitadorTaxa(2, 60, relogio=lambda: instante[0])
    assert limitador.permitir("a") and limitador.permitir("a")
    assert not limitador.permitir("a")
    assert limitador.permitir("b")
    instante[0] = 59.9
    assert not limitador.permitir("a")
    instante[0] = 60.0
    assert limitador.permitir("a")


def test_limitador_remove_chaves_expiradas(monkeypatch):
    monkeypatch.setattr("src.auth.rate_limit.LIMPEZA_ACIMA_DE_CHAVES", 2)
    instante = [0.0]
    limitador = LimitadorTaxa(1, 60, relogio=lambda: instante[0])
    for chave in "abc":
        limitador.permitir(chave)
    instante[0] = 100.0
    limitador.permitir("d")
    assert set(limitador._eventos) == {"d"}


# Script de hash


def test_gerar_hash_produz_hash_verificavel():
    valor = gerar_hash("uma-senha-boa")
    assert valor.startswith("$2b$")
    assert bcrypt.checkpw(b"uma-senha-boa", valor.encode())


@pytest.mark.parametrize("senha", ["curta", "x" * 73])
def test_gerar_hash_rejeita_tamanho_invalido(senha):
    with pytest.raises(ValueError):
        gerar_hash(senha)
