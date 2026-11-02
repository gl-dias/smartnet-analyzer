"""Traduz texto em operações sobre o grafo (Anthropic) e valida as operações sem aplicá-las."""

import copy
import json
import logging
from typing import Literal

import anthropic
from pydantic import BaseModel, StrictBool, StrictFloat, StrictInt, StrictStr, ValidationError

from src import config
from src.core.algoritmos.comum import exigir_vertices
from src.core.grafo import ErroGrafo, ListaAdjacencia
from src.ia.prompts import FERRAMENTA, NOME_FERRAMENTA, SISTEMA

MAX_TOKENS = 4000
TEMPO_LIMITE_SEGUNDOS = 60
NOMES_ALGORITMOS = {"dfs": "DFS", "bfs": "BFS", "dijkstra": "Dijkstra", "kruskal": "Kruskal"}

# Modelos que aceitam nova tentativa automática no servidor quando o pedido é recusado.
MODELOS_COM_FALLBACK = frozenset(
    {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}
)

AVISO_ENTRADA_MANUAL = "Enquanto isso, use as abas Manual, Texto ou Importar/Exemplos."

logger = logging.getLogger(__name__)


class ErroIA(Exception):
    """Falha ao consultar a IA. A mensagem é exibida ao usuário."""


class Operacao(BaseModel):
    tipo: Literal[
        "definir_tipo",
        "adicionar_vertice",
        "remover_vertice",
        "adicionar_aresta",
        "remover_aresta",
        "alterar_peso",
        "limpar_grafo",
        "executar_algoritmo",
    ]
    direcionado: StrictBool | None = None
    ponderado: StrictBool | None = None
    vertice: StrictStr | None = None
    origem: StrictStr | None = None
    destino: StrictStr | None = None
    peso: StrictInt | StrictFloat | None = None
    algoritmo: Literal["dfs", "bfs", "dijkstra", "kruskal"] | None = None


# Chamada à API


def _criar_cliente():
    return anthropic.Anthropic(
        api_key=config.ANTHROPIC_API_KEY, timeout=TEMPO_LIMITE_SEGUNDOS, max_retries=1
    )


def _mensagem_usuario(texto, canal, dados):
    contexto = {
        "direcionado": dados["direcionado"],
        "ponderado": dados["ponderado"],
        "vertices": dados["vertices"],
        "arestas": [
            [a["origem"], a["destino"], a.get("peso")] if dados["ponderado"] else [a["origem"], a["destino"]]
            for a in dados["arestas"]
        ],
    }
    return (
        f"Grafo atual: {json.dumps(contexto, ensure_ascii=False)}\n"
        f"Canal: {canal}\n\n<pedido>\n{texto}\n</pedido>"
    )


def _chamar_modelo(texto, canal, dados):
    parametros = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SISTEMA,
        "tools": [FERRAMENTA],
        # A API recusa tool_choice forçado neste modelo, com ou sem thinking ("tool_choice: type
        # "tool" and "any" are not supported for this model"). strict garante os argumentos e o
        # prompt exige a chamada, que é conferida em _ler_resposta.
        "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
        "output_config": {"effort": "low"},
        "messages": [{"role": "user", "content": _mensagem_usuario(texto, canal, dados)}],
    }
    cliente = _criar_cliente()
    try:
        if config.ANTHROPIC_MODEL in MODELOS_COM_FALLBACK:
            return cliente.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **parametros
            )
        return cliente.messages.create(**parametros)
    except anthropic.AuthenticationError as erro:
        logger.error("Chave da Anthropic recusada: %s", erro)
        raise ErroIA(f"A chave da IA foi recusada. {AVISO_ENTRADA_MANUAL}") from erro
    except anthropic.NotFoundError as erro:
        logger.error("Modelo indisponível (%s): %s", config.ANTHROPIC_MODEL, erro)
        raise ErroIA(f"O modelo de IA configurado não está disponível. {AVISO_ENTRADA_MANUAL}") from erro
    except anthropic.RateLimitError as erro:
        raise ErroIA(f"A IA está sobrecarregada, tente em instantes. {AVISO_ENTRADA_MANUAL}") from erro
    except anthropic.APIStatusError as erro:
        logger.error("Erro da API Anthropic (%s): %s", erro.status_code, erro)
        raise ErroIA(f"A IA não conseguiu responder agora. {AVISO_ENTRADA_MANUAL}") from erro
    except anthropic.APIConnectionError as erro:
        logger.error("Falha de conexão com a Anthropic: %s", erro)
        raise ErroIA(f"Não foi possível falar com a IA. {AVISO_ENTRADA_MANUAL}") from erro


def _registrar_resposta(resposta):
    """Registra qual modelo respondeu de fato, que difere do pedido quando há fallback."""
    nivel = logging.INFO if resposta.model == config.ANTHROPIC_MODEL else logging.WARNING
    logger.log(
        nivel,
        "IA: pedido=%s respondeu=%s parada=%s tokens=%s+%s request_id=%s",
        config.ANTHROPIC_MODEL,
        resposta.model,
        resposta.stop_reason,
        resposta.usage.input_tokens,
        resposta.usage.output_tokens,
        resposta._request_id,
    )


def _ler_resposta(resposta):
    _registrar_resposta(resposta)
    if resposta.stop_reason == "refusal":
        raise ErroIA("A IA não pôde processar este pedido. Tente reescrevê-lo.")
    if resposta.stop_reason == "max_tokens":
        raise ErroIA("A descrição gerou operações demais de uma vez. Envie o grafo em partes menores.")

    chamada = next(
        (b for b in resposta.content if b.type == "tool_use" and b.name == NOME_FERRAMENTA), None
    )
    if chamada is None:
        # Sem tool_choice forçado, o modelo pode responder em texto. Isso nunca vira operação.
        texto = " ".join(b.text for b in resposta.content if b.type == "text").strip()
        return {"tipo": "pergunta", "pergunta": texto or "Não entendi o pedido. Pode reformular?"}

    pergunta = chamada.input.get("pergunta_esclarecimento")
    if pergunta:
        return {"tipo": "pergunta", "pergunta": pergunta}
    try:
        operacoes = [Operacao.model_validate(item) for item in chamada.input.get("operacoes", [])]
    except ValidationError as erro:
        logger.error("Operações fora do esquema: %s", erro)
        raise ErroIA("A IA devolveu uma resposta inválida. Tente novamente.") from erro
    if not operacoes:
        return {"tipo": "pergunta", "pergunta": "Não encontrei nenhuma mudança no pedido. Pode detalhar?"}
    return {"tipo": "operacoes", "operacoes": operacoes}


def interpretar(texto, canal, dados):
    """Consulta o modelo. Devolve operações ainda não validadas ou uma pergunta."""
    if not config.ANTHROPIC_API_KEY:
        raise ErroIA(f"A IA não está configurada neste servidor. {AVISO_ENTRADA_MANUAL}")
    return _ler_resposta(_chamar_modelo(texto, canal, dados))


# Validação das operações


def _simbolo(dados):
    return "→" if dados["direcionado"] else "↔"


def _nome(valor):
    return valor if valor else "?"


def _localizar_aresta(dados, origem, destino):
    """Índice da aresta na lista do estado, em qualquer sentido se não direcionado."""
    for indice, aresta in enumerate(dados["arestas"]):
        mesmo = aresta["origem"] == origem and aresta["destino"] == destino
        inverso = aresta["origem"] == destino and aresta["destino"] == origem
        if mesmo or (inverso and not dados["direcionado"]):
            return indice
    return -1


def _descrever(op, dados):
    """Texto legível da operação, para a tela de revisão."""
    via = f"{_nome(op.origem)} {_simbolo(dados)} {_nome(op.destino)}"
    if op.tipo == "definir_tipo":
        partes = []
        if op.direcionado is not None:
            partes.append("direcionado" if op.direcionado else "não direcionado")
        if op.ponderado is not None:
            partes.append("ponderado" if op.ponderado else "sem peso")
        return f"Tornar o grafo {' e '.join(partes)}" if partes else "Alterar o tipo do grafo"
    if op.tipo == "adicionar_vertice":
        return f"+ bairro {_nome(op.vertice)}"
    if op.tipo == "remover_vertice":
        return f"- bairro {_nome(op.vertice)} (e suas vias)"
    if op.tipo == "adicionar_aresta":
        return f"+ via {via}, custo {op.peso}" if op.peso is not None else f"+ via {via}"
    if op.tipo == "remover_aresta":
        return f"- via {via}"
    if op.tipo == "alterar_peso":
        indice = _localizar_aresta(dados, op.origem, op.destino)
        antes = f"de {dados['arestas'][indice].get('peso', 1)} " if indice >= 0 else ""
        return f"~ via {via}: custo {antes}para {op.peso}"
    if op.tipo == "limpar_grafo":
        return "Apagar todo o grafo"
    nome = NOMES_ALGORITMOS.get(op.algoritmo, "algoritmo")
    if op.algoritmo == "kruskal":
        return f"Executar {nome}"
    destino = f" até {op.destino}" if op.destino else ""
    return f"Executar {nome} a partir de {_nome(op.origem)}{destino}"


def _definir_tipo(dados, op):
    if op.direcionado is None and op.ponderado is None:
        raise ErroGrafo("Informe o que muda no tipo do grafo.")
    avisos = []
    if op.direcionado is False and dados["direcionado"]:
        # A -> B e B -> A viram a mesma via sem direção: fica a primeira cadastrada.
        primeiras = {}
        restantes = []
        for aresta in dados["arestas"]:
            par = frozenset((aresta["origem"], aresta["destino"]))
            if par in primeiras:
                mantida = primeiras[par]
                avisos.append(
                    f"{mantida['origem']} ↔ {mantida['destino']} (ficou peso {mantida.get('peso', 1)}, "
                    f"descartado {aresta.get('peso', 1)})"
                )
            else:
                primeiras[par] = aresta
                restantes.append(aresta)
        dados["arestas"] = restantes
    if op.direcionado is not None:
        dados["direcionado"] = op.direcionado
    if op.ponderado is not None:
        dados["ponderado"] = op.ponderado
        if op.ponderado:
            for aresta in dados["arestas"]:
                aresta.setdefault("peso", 1)
    return f"Vias fundidas: {'; '.join(avisos)}." if avisos else None


def _aplicar(dados, op):
    """Aplica a operação em dados, validando pela própria lista de adjacência.

    As arestas continuam no estado como o usuário as inseriu, com sentido e peso
    preservados. Devolve um aviso opcional. Levanta ErroGrafo se a operação for inválida.
    """
    grafo = ListaAdjacencia.from_json(dados)
    if op.tipo == "definir_tipo":
        return _definir_tipo(dados, op)
    if op.tipo == "adicionar_vertice":
        dados["vertices"].append(grafo.adicionar_vertice(op.vertice))
    elif op.tipo == "remover_vertice":
        grafo.remover_vertice(op.vertice)
        dados["vertices"].remove(op.vertice)
        dados["arestas"] = [
            a for a in dados["arestas"] if op.vertice not in (a["origem"], a["destino"])
        ]
    elif op.tipo == "adicionar_aresta":
        for vertice in (op.origem, op.destino):
            if not vertice or not grafo.tem_vertice(vertice):
                raise ErroGrafo(f"O vértice {_nome(vertice)} não existe.")
        if dados["ponderado"] and op.peso is None:
            raise ErroGrafo(f"Falta o custo da via {op.origem} e {op.destino}.")
        grafo.adicionar_aresta(op.origem, op.destino, op.peso if op.peso is not None else 1)
        aresta = {"origem": op.origem, "destino": op.destino}
        if dados["ponderado"]:
            aresta["peso"] = op.peso
        dados["arestas"].append(aresta)
    elif op.tipo == "remover_aresta":
        grafo.remover_aresta(op.origem, op.destino)
        del dados["arestas"][_localizar_aresta(dados, op.origem, op.destino)]
    elif op.tipo == "alterar_peso":
        if op.peso is None:
            raise ErroGrafo("Falta o novo custo da via.")
        grafo.alterar_peso(op.origem, op.destino, op.peso)
        dados["arestas"][_localizar_aresta(dados, op.origem, op.destino)]["peso"] = op.peso
    elif op.tipo == "limpar_grafo":
        dados["vertices"] = []
        dados["arestas"] = []
    elif op.tipo == "executar_algoritmo":
        if op.algoritmo is None:
            raise ErroGrafo("Falta informar o algoritmo.")
        if op.algoritmo != "kruskal":
            exigir_vertices(grafo, op.origem, op.destino or None)
    return None


def simular(dados, operacoes):
    """Valida as operações em sequência sobre uma cópia do grafo, sem aplicar nada de fato.

    Uma operação inválida recebe a mensagem em `erro` e é ignorada, sem impedir as
    seguintes. Devolve as operações anotadas e o grafo resultante.
    """
    atual = copy.deepcopy(dados)
    atual["vertices"] = ListaAdjacencia.from_json(atual).vertices()
    anotadas = []
    for op in operacoes:
        descricao = _descrever(op, atual)
        candidato = copy.deepcopy(atual)
        erro = aviso = None
        try:
            aviso = _aplicar(candidato, op)
            ListaAdjacencia.from_json(candidato)
            atual = candidato
        except ErroGrafo as falha:
            erro = str(falha)
        anotadas.append({**op.model_dump(), "descricao": descricao, "erro": erro, "aviso": aviso})
    return {"operacoes": anotadas, "grafo": atual}
