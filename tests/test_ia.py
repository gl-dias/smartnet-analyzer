"""Testes do interpretador, sempre com um cliente simulado: nenhum chama a API de verdade."""

import logging
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from src import config
from src.api import rotas_ia
from src.app import app
from src.ia import interpretador, prompts
from src.ia.interpretador import Operacao, simular
from tests.conftest import SENHA_TESTE, USUARIO_TESTE

GRAFO = {
    "direcionado": False,
    "ponderado": True,
    "vertices": ["O", "A", "B"],
    "arestas": [
        {"origem": "O", "destino": "A", "peso": 2},
        {"origem": "B", "destino": "A", "peso": 3},
    ],
}


def op(tipo, **campos):
    return Operacao(tipo=tipo, **campos)


def bloco_ferramenta(operacoes=(), pergunta=None):
    entrada = {"pergunta_esclarecimento": pergunta, "operacoes": list(operacoes)}
    return SimpleNamespace(type="tool_use", name=prompts.NOME_FERRAMENTA, input=entrada)


def resposta_modelo(*blocos, stop_reason="tool_use", modelo="claude-sonnet-5-5"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=list(blocos),
        model=modelo,
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        _request_id="req_teste",
    )


class ClienteFalso:
    """Registra os parâmetros da chamada e devolve a resposta ou o erro configurado."""

    def __init__(self, resultado):
        self.resultado = resultado
        self.chamadas = []
        criar = SimpleNamespace(create=self._criar)
        self.messages = criar
        self.beta = SimpleNamespace(messages=criar)

    def _criar(self, **parametros):
        self.chamadas.append(parametros)
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


@pytest.fixture
def com_ia(monkeypatch):
    """Liga a IA com o cliente falso. Devolve a função que define o resultado da chamada."""
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "chave-falsa")
    monkeypatch.setattr(config, "ANTHROPIC_MODEL", "claude-sonnet-5-5")

    def configurar(resultado):
        falso = ClienteFalso(resultado)
        monkeypatch.setattr(interpretador, "_criar_cliente", lambda: falso)
        return falso

    return configurar


@pytest.fixture
def cliente():
    logado = TestClient(app)
    assert logado.post("/login", json={"usuario": USUARIO_TESTE, "senha": SENHA_TESTE}).status_code == 200
    return logado


def interpretar_http(cliente, texto="adicione algo", canal="texto", grafo=GRAFO):
    return cliente.post("/api/interpretar", json={"texto": texto, "canal": canal, "grafo": grafo})


ADICIONAR_T = {
    "tipo": "adicionar_vertice", "direcionado": None, "ponderado": None, "vertice": "T",
    "origem": None, "destino": None, "peso": None, "algoritmo": None,
}
VIA_T = {
    "tipo": "adicionar_aresta", "direcionado": None, "ponderado": None, "vertice": None,
    "origem": "T", "destino": "O", "peso": 5, "algoritmo": None,
}


# Chamada à API


def test_parametros_da_chamada_respeitam_os_limites(com_ia, cliente):
    falso = com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    assert interpretar_http(cliente, "adicione o bairro T", "voz").status_code == 200
    chamada = falso.chamadas[0]
    assert chamada["max_tokens"] == 4000
    assert chamada["model"] == "claude-sonnet-5-5"
    assert chamada["tool_choice"]["type"] == "auto"
    assert chamada["tools"][0]["strict"] is True
    assert chamada["fallbacks"] == "default"
    conteudo = chamada["messages"][0]["content"]
    assert "adicione o bairro T" in conteudo
    assert "Canal: voz" in conteudo
    assert '"vertices": ["O", "A", "B"]' in conteudo


def test_modelo_sem_fallback_nao_envia_o_parametro(com_ia, cliente, monkeypatch):
    falso = com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    monkeypatch.setattr(config, "ANTHROPIC_MODEL", "claude-haiku-5-5")
    assert interpretar_http(cliente).status_code == 200
    assert falso.chamadas[0]["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in falso.chamadas[0]


def test_log_registra_o_modelo_que_respondeu(com_ia, cliente, caplog):
    com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    with caplog.at_level(logging.INFO, logger="src.ia.interpretador"):
        interpretar_http(cliente)
    registro = caplog.records[-1]
    assert registro.levelno == logging.INFO
    assert "pedido=claude-sonnet-5-5 respondeu=claude-sonnet-5-5" in registro.getMessage()
    assert "tokens=10+5 request_id=req_teste" in registro.getMessage()


def test_fallback_gera_alerta_com_o_modelo_substituto(com_ia, cliente, caplog):
    com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T]), modelo="claude-sonnet-5"))
    with caplog.at_level(logging.INFO, logger="src.ia.interpretador"):
        interpretar_http(cliente)
    registro = caplog.records[-1]
    assert registro.levelno == logging.WARNING
    assert "respondeu=claude-sonnet-5 " in registro.getMessage()


def test_log_nao_registra_o_texto_do_usuario(com_ia, cliente, caplog):
    com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    with caplog.at_level(logging.INFO, logger="src.ia.interpretador"):
        interpretar_http(cliente, "frase-sigilosa")
    assert "frase-sigilosa" not in caplog.text


def test_esquema_estrito_exige_todos_os_campos():
    esquema = prompts.FERRAMENTA["input_schema"]
    assert esquema["additionalProperties"] is False
    item = esquema["properties"]["operacoes"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    # A API recusa enum junto de type com null: o nulo precisa vir em um anyOf.
    assert not any("enum" in campo and isinstance(campo.get("type"), list)
                   for campo in item["properties"].values())
    assert set(item["properties"]["tipo"]["enum"]) == set(
        Operacao.model_fields["tipo"].annotation.__args__
    )


def test_interpretar_nao_aplica_e_devolve_operacoes_validadas(com_ia, cliente):
    com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T, VIA_T])))
    corpo = interpretar_http(cliente).json()
    assert corpo["tipo"] == "operacoes"
    assert [o["descricao"] for o in corpo["operacoes"]] == ["+ bairro T", "+ via T ↔ O, custo 5"]
    assert all(o["erro"] is None for o in corpo["operacoes"])
    assert "T" in corpo["grafo"]["vertices"]
    assert corpo["estrutura"]["estatisticas"]["arestas"] == 3
    assert "T" not in GRAFO["vertices"]


def test_pergunta_de_esclarecimento_nao_traz_operacoes(com_ia, cliente):
    com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T], pergunta="Qual o custo da via?")))
    assert interpretar_http(cliente).json() == {"tipo": "pergunta", "pergunta": "Qual o custo da via?"}


def test_resposta_em_texto_vira_pergunta_e_nunca_operacao(com_ia, cliente):
    texto = SimpleNamespace(type="text", text="Qual bairro?")
    com_ia(resposta_modelo(texto, stop_reason="end_turn"))
    assert interpretar_http(cliente).json() == {"tipo": "pergunta", "pergunta": "Qual bairro?"}


def test_lista_vazia_sem_pergunta_vira_pergunta(com_ia, cliente):
    com_ia(resposta_modelo(bloco_ferramenta([])))
    assert interpretar_http(cliente).json()["tipo"] == "pergunta"


def test_blocos_de_thinking_sao_ignorados(com_ia, cliente):
    pensamento = SimpleNamespace(type="thinking", thinking="")
    com_ia(resposta_modelo(pensamento, bloco_ferramenta([ADICIONAR_T])))
    assert interpretar_http(cliente).json()["tipo"] == "operacoes"


@pytest.mark.parametrize(
    "stop_reason, trecho", [("refusal", "reescrevê-lo"), ("max_tokens", "partes menores")]
)
def test_parada_antecipada_nao_usa_a_saida_parcial(com_ia, cliente, stop_reason, trecho):
    com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T]), stop_reason=stop_reason))
    resposta = interpretar_http(cliente)
    assert resposta.status_code == 503
    assert trecho in resposta.json()["erro"]


def test_operacao_fora_do_esquema_e_recusada(com_ia, cliente):
    com_ia(resposta_modelo(bloco_ferramenta([{**ADICIONAR_T, "tipo": "apagar_banco"}])))
    assert interpretar_http(cliente).status_code == 503


def erro_status(classe, status):
    pedido = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return classe("falha", response=httpx2.Response(status, request=pedido), body=None)


@pytest.mark.parametrize(
    "erro",
    [
        erro_status(anthropic.AuthenticationError, 401),
        erro_status(anthropic.NotFoundError, 404),
        erro_status(anthropic.RateLimitError, 429),
        erro_status(anthropic.BadRequestError, 400),
        erro_status(anthropic.InternalServerError, 500),
        anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")),
    ],
)
def test_servico_fora_do_ar_gera_aviso_amigavel(com_ia, cliente, erro):
    com_ia(erro)
    resposta = interpretar_http(cliente)
    assert resposta.status_code == 503
    assert "Manual" in resposta.json()["erro"]


def test_sem_chave_avisa_e_o_restante_funciona(cliente):
    resposta = interpretar_http(cliente)
    assert resposta.status_code == 503
    assert "não está configurada" in resposta.json()["erro"]
    assert cliente.post("/api/algoritmos/kruskal", json={"grafo": GRAFO}).status_code == 200


# Limites de custo


def test_texto_acima_do_limite_nao_chama_a_api(com_ia, cliente):
    falso = com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    resposta = interpretar_http(cliente, "x" * 2001)
    assert resposta.status_code == 422
    assert "2000" in resposta.json()["erro"]
    assert falso.chamadas == []
    assert interpretar_http(cliente, "x" * 2000).status_code == 200


@pytest.mark.parametrize("texto", ["", "   \n "])
def test_texto_vazio_nao_chama_a_api(com_ia, cliente, texto):
    falso = com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    assert interpretar_http(cliente, texto).status_code == 422
    assert falso.chamadas == []


def test_grafo_grande_demais_nao_chama_a_api(com_ia, cliente):
    falso = com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    grande = {"ponderado": False, "vertices": [f"V{i}" for i in range(201)]}
    assert interpretar_http(cliente, grafo=grande).status_code == 422
    assert falso.chamadas == []


def test_grafo_invalido_nao_chama_a_api(com_ia, cliente):
    falso = com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    grafo = {"vertices": ["A", "A"]}
    assert interpretar_http(cliente, grafo=grafo).status_code == 422
    assert falso.chamadas == []


def test_limite_de_30_chamadas_por_sessao(com_ia, cliente):
    falso = com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    for _ in range(30):
        assert interpretar_http(cliente).status_code == 200
    bloqueada = interpretar_http(cliente)
    assert bloqueada.status_code == 429
    assert "30" in bloqueada.json()["erro"]
    assert len(falso.chamadas) == 30

    outra_sessao = TestClient(app)
    outra_sessao.post("/login", json={"usuario": USUARIO_TESTE, "senha": SENHA_TESTE})
    assert interpretar_http(outra_sessao).status_code == 200


def test_texto_rejeitado_nao_consome_o_limite(com_ia, cliente):
    com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    for _ in range(31):
        interpretar_http(cliente, "")
    assert interpretar_http(cliente).status_code == 200


def test_rotas_de_ia_exigem_sessao(com_ia):
    falso = com_ia(resposta_modelo(bloco_ferramenta([ADICIONAR_T])))
    anonimo = TestClient(app)
    assert interpretar_http(anonimo).status_code == 401
    previa = anonimo.post("/api/operacoes/previa", json={"grafo": GRAFO, "operacoes": []})
    assert previa.status_code == 401
    assert falso.chamadas == []


def test_canal_invalido(cliente):
    assert interpretar_http(cliente, canal="telepatia").status_code == 422


# Validação das operações


def test_cada_operacao_e_aplicada_em_sequencia():
    resultado = simular(GRAFO, [
        op("adicionar_vertice", vertice="T"),
        op("adicionar_aresta", origem="T", destino="O", peso=5),
        op("alterar_peso", origem="A", destino="O", peso=6),
        op("remover_aresta", origem="A", destino="B"),
    ])
    assert [o["erro"] for o in resultado["operacoes"]] == [None] * 4
    assert [o["descricao"] for o in resultado["operacoes"]] == [
        "+ bairro T",
        "+ via T ↔ O, custo 5",
        "~ via A ↔ O: custo de 2 para 6",
        "- via A ↔ B",
    ]
    assert resultado["grafo"]["arestas"] == [
        {"origem": "O", "destino": "A", "peso": 6},
        {"origem": "T", "destino": "O", "peso": 5},
    ]


def test_simular_nao_altera_o_grafo_recebido():
    original = {**GRAFO, "arestas": [dict(a) for a in GRAFO["arestas"]]}
    simular(original, [op("limpar_grafo")])
    assert original["arestas"] == GRAFO["arestas"]
    assert original["vertices"] == GRAFO["vertices"]


@pytest.mark.parametrize(
    "operacao, trecho",
    [
        (op("adicionar_vertice", vertice="O"), "já existe"),
        (op("adicionar_vertice"), "texto"),
        (op("remover_vertice", vertice="Z"), "não existe"),
        (op("adicionar_aresta", origem="O", destino="Z", peso=1), "Z não existe"),
        (op("adicionar_aresta", origem="O", destino="A", peso=1), "já existe"),
        (op("adicionar_aresta", origem="A", destino="O", peso=1), "já existe"),
        (op("adicionar_aresta", origem="O", destino="B"), "Falta o custo"),
        (op("remover_aresta", origem="O", destino="B"), "não existe"),
        (op("alterar_peso", origem="O", destino="B", peso=1), "não existe"),
        (op("alterar_peso", origem="O", destino="A"), "Falta o novo custo"),
        (op("definir_tipo"), "Informe"),
        (op("executar_algoritmo"), "algoritmo"),
        (op("executar_algoritmo", algoritmo="dfs"), "origem"),
        (op("executar_algoritmo", algoritmo="bfs", origem="Z"), "não existe"),
        (op("executar_algoritmo", algoritmo="dijkstra", origem="O", destino="Z"), "destino"),
    ],
)
def test_operacao_invalida_recebe_mensagem_e_nao_muda_o_grafo(operacao, trecho):
    resultado = simular(GRAFO, [operacao])
    assert trecho in resultado["operacoes"][0]["erro"]
    assert resultado["grafo"]["vertices"] == ["A", "B", "O"]
    assert len(resultado["grafo"]["arestas"]) == 2


def test_operacao_invalida_nao_impede_as_seguintes():
    resultado = simular(GRAFO, [
        op("remover_vertice", vertice="Z"),
        op("adicionar_vertice", vertice="T"),
    ])
    assert resultado["operacoes"][0]["erro"]
    assert resultado["operacoes"][1]["erro"] is None
    assert "T" in resultado["grafo"]["vertices"]


def test_via_depende_de_o_bairro_ter_sido_criado_antes():
    resultado = simular(GRAFO, [
        op("adicionar_aresta", origem="T", destino="O", peso=5),
        op("adicionar_vertice", vertice="T"),
    ])
    assert "não existe" in resultado["operacoes"][0]["erro"]


def test_duplicata_na_mesma_resposta_e_detectada():
    resultado = simular(GRAFO, [
        op("adicionar_aresta", origem="O", destino="B", peso=1),
        op("adicionar_aresta", origem="B", destino="O", peso=2),
    ])
    assert resultado["operacoes"][0]["erro"] is None
    assert "já existe" in resultado["operacoes"][1]["erro"]


def test_remover_bairro_leva_as_vias_junto():
    resultado = simular(GRAFO, [op("remover_vertice", vertice="A")])
    assert resultado["grafo"]["vertices"] == ["B", "O"]
    assert resultado["grafo"]["arestas"] == []


def test_limpar_mantem_o_tipo():
    grafo = {**GRAFO, "direcionado": True, "arestas": []}
    resultado = simular(grafo, [op("limpar_grafo")])
    assert resultado["grafo"] == {"direcionado": True, "ponderado": True, "vertices": [], "arestas": []}


def test_definir_direcionado_preserva_o_sentido_cadastrado():
    resultado = simular(GRAFO, [op("definir_tipo", direcionado=True)])
    assert resultado["grafo"]["direcionado"] is True
    assert resultado["grafo"]["arestas"][1] == {"origem": "B", "destino": "A", "peso": 3}
    assert resultado["operacoes"][0]["descricao"] == "Tornar o grafo direcionado"


def test_definir_nao_direcionado_funde_e_avisa_o_peso_que_ficou():
    grafo = {
        "direcionado": True, "ponderado": True, "vertices": ["A", "B"],
        "arestas": [
            {"origem": "A", "destino": "B", "peso": 1},
            {"origem": "B", "destino": "A", "peso": 2},
        ],
    }
    resultado = simular(grafo, [op("definir_tipo", direcionado=False)])
    assert resultado["grafo"]["arestas"] == [{"origem": "A", "destino": "B", "peso": 1}]
    assert "A ↔ B (ficou peso 1, descartado 2)" in resultado["operacoes"][0]["aviso"]


def test_ligar_ponderado_da_peso_1_para_vias_sem_peso():
    grafo = {"direcionado": False, "ponderado": False, "vertices": ["A", "B"],
             "arestas": [{"origem": "A", "destino": "B"}]}
    resultado = simular(grafo, [op("definir_tipo", ponderado=True)])
    assert resultado["grafo"]["arestas"][0]["peso"] == 1


def test_via_em_grafo_sem_peso_nao_exige_custo():
    grafo = {"direcionado": False, "ponderado": False, "vertices": ["A", "B"], "arestas": []}
    resultado = simular(grafo, [op("adicionar_aresta", origem="A", destino="B")])
    assert resultado["operacoes"][0]["erro"] is None
    assert resultado["operacoes"][0]["descricao"] == "+ via A ↔ B"
    assert resultado["grafo"]["arestas"] == [{"origem": "A", "destino": "B"}]


def test_grafo_direcionado_descreve_com_seta_e_diferencia_sentidos():
    grafo = {"direcionado": True, "ponderado": True, "vertices": ["A", "B"],
             "arestas": [{"origem": "A", "destino": "B", "peso": 1}]}
    resultado = simular(grafo, [
        op("adicionar_aresta", origem="B", destino="A", peso=2),
        op("remover_aresta", origem="A", destino="B"),
    ])
    assert resultado["operacoes"][0]["descricao"] == "+ via B → A, custo 2"
    assert resultado["grafo"]["arestas"] == [{"origem": "B", "destino": "A", "peso": 2}]


def test_executar_algoritmo_e_validado_sem_mudar_o_grafo():
    resultado = simular(GRAFO, [
        op("executar_algoritmo", algoritmo="dijkstra", origem="O", destino="B"),
        op("executar_algoritmo", algoritmo="kruskal"),
    ])
    assert [o["descricao"] for o in resultado["operacoes"]] == [
        "Executar Dijkstra a partir de O até B",
        "Executar Kruskal",
    ]
    assert all(o["erro"] is None for o in resultado["operacoes"])


def test_algoritmo_usa_o_grafo_ja_alterado_pelas_operacoes_anteriores():
    resultado = simular(GRAFO, [
        op("adicionar_vertice", vertice="T"),
        op("executar_algoritmo", algoritmo="bfs", origem="T"),
    ])
    assert resultado["operacoes"][1]["erro"] is None


# Prévia


def test_previa_revalida_as_operacoes_marcadas(cliente):
    resposta = cliente.post("/api/operacoes/previa", json={
        "grafo": GRAFO,
        "operacoes": [
            {"tipo": "adicionar_aresta", "origem": "T", "destino": "O", "peso": 5},
        ],
    })
    assert resposta.status_code == 200
    assert "T não existe" in resposta.json()["operacoes"][0]["erro"]
    assert resposta.json()["estrutura"]["estatisticas"]["vertices"] == 3


def test_previa_recusa_tipo_de_operacao_desconhecido(cliente):
    resposta = cliente.post("/api/operacoes/previa", json={
        "grafo": GRAFO, "operacoes": [{"tipo": "formatar_disco"}],
    })
    assert resposta.status_code == 422
    assert "valor não permitido" in resposta.json()["erro"]


def test_previa_recusa_peso_nao_numerico(cliente):
    resposta = cliente.post("/api/operacoes/previa", json={
        "grafo": GRAFO,
        "operacoes": [{"tipo": "alterar_peso", "origem": "O", "destino": "A", "peso": "barato"}],
    })
    assert resposta.status_code == 422


def test_limites_das_rotas_estao_nos_valores_especificados():
    assert rotas_ia.MAXIMO_CARACTERES == 2000
    assert rotas_ia.limitador_ia.maximo == 30
    assert rotas_ia.limitador_ia.janela_segundos == 3600
    assert interpretador.MAX_TOKENS == 4000
