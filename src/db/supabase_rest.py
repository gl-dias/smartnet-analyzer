"""Acesso ao Supabase pela API REST (PostgREST). A chave de servidor nunca sai do backend."""

import logging
from datetime import datetime, timezone

import httpx

from src import config

TEMPO_LIMITE_SEGUNDOS = 8
MAXIMO_LISTAGEM = 100
MENSAGEM_INDISPONIVEL = (
    "O banco de dados está indisponível agora. O restante da aplicação continua "
    "funcionando, e você pode guardar o grafo com Exportar JSON."
)

logger = logging.getLogger(__name__)


class ErroSupabase(Exception):
    """Falha ao falar com o banco. Os detalhes vão só para o log."""


def configurado():
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def _cabecalhos():
    """As chaves novas (sb_secret_) não são JWT e não podem ir em Authorization."""
    chave = config.SUPABASE_SERVICE_KEY
    if chave.startswith("sb_"):
        return {"apikey": chave}
    return {"apikey": chave, "Authorization": f"Bearer {chave}"}


def _criar_cliente():
    return httpx.Client(timeout=TEMPO_LIMITE_SEGUNDOS)


def _requisitar(metodo, tabela, params=None, corpo=None, prefer=None):
    if not configurado():
        raise ErroSupabase("Supabase não configurado.")
    url = f"{config.SUPABASE_URL.rstrip('/')}/rest/v1/{tabela}"
    cabecalhos = _cabecalhos()
    if prefer:
        cabecalhos["Prefer"] = prefer
    try:
        with _criar_cliente() as cliente:
            resposta = cliente.request(metodo, url, params=params, json=corpo, headers=cabecalhos)
    except httpx.HTTPError as erro:
        logger.warning("Supabase: falha de conexão em %s %s: %s", metodo, tabela, type(erro).__name__)
        raise ErroSupabase("Falha de conexão.") from erro
    if resposta.is_error:
        logger.warning("Supabase: %s %s devolveu %s", metodo, tabela, resposta.status_code)
        raise ErroSupabase(f"Status {resposta.status_code}.")
    return resposta.json() if resposta.content else None


def registrar_sem_falhar(funcao, *argumentos):
    """Registro de auditoria: se o banco falhar, avisa no log e a aplicação segue."""
    if not configurado():
        return
    try:
        funcao(*argumentos)
    except ErroSupabase:
        logger.warning("Supabase: registro %s não foi gravado.", funcao.__name__)


# Sessões


def registrar_sessao(sessao_id):
    """Cria a sessão se ainda não existir, pois o login pode ter ocorrido com o banco fora do ar."""
    _requisitar(
        "POST",
        "sessoes",
        params={"on_conflict": "id"},
        corpo={"id": sessao_id},
        prefer="resolution=ignore-duplicates,return=minimal",
    )


def finalizar_sessao(sessao_id):
    _requisitar(
        "PATCH",
        "sessoes",
        params={"id": f"eq.{sessao_id}"},
        corpo={"finalizada_em": datetime.now(timezone.utc).isoformat()},
        prefer="return=minimal",
    )


# Grafos


def salvar_grafo(sessao_id, nome, dados, origem_entrada):
    if sessao_id:
        registrar_sessao(sessao_id)
    linhas = _requisitar(
        "POST",
        "grafos",
        params={"select": "id,nome,criado_em"},
        corpo={
            "sessao_id": sessao_id,
            "nome": nome,
            "direcionado": dados["direcionado"],
            "ponderado": dados["ponderado"],
            "vertices": dados["vertices"],
            "arestas": dados["arestas"],
            "origem_entrada": origem_entrada,
        },
        prefer="return=representation",
    )
    return linhas[0]


def listar_grafos():
    return _requisitar(
        "GET",
        "grafos",
        params={
            "select": "id,nome,direcionado,ponderado,origem_entrada,criado_em",
            "order": "criado_em.desc",
            "limit": MAXIMO_LISTAGEM,
        },
    )


def buscar_grafo(grafo_id):
    linhas = _requisitar(
        "GET",
        "grafos",
        params={
            "id": f"eq.{grafo_id}",
            "select": "id,nome,direcionado,ponderado,vertices,arestas,origem_entrada,criado_em",
        },
    )
    return linhas[0] if linhas else None


def apagar_grafo(grafo_id):
    """Devolve False se o grafo não existia."""
    linhas = _requisitar(
        "DELETE",
        "grafos",
        params={"id": f"eq.{grafo_id}", "select": "id"},
        prefer="return=representation",
    )
    return bool(linhas)


# Auditoria


def registrar_execucao(grafo_id, algoritmo, parametros, resultado, tempo_ms):
    _requisitar(
        "POST",
        "execucoes",
        corpo={
            "grafo_id": grafo_id,
            "algoritmo": algoritmo,
            "parametros": parametros,
            "resultado": resultado,
            "tempo_ms": tempo_ms,
        },
        prefer="return=minimal",
    )


def registrar_interpretacao(interpretacao_id, sessao_id, texto, canal, operacoes):
    if sessao_id:
        registrar_sessao(sessao_id)
    _requisitar(
        "POST",
        "interpretacoes_ia",
        corpo={
            "id": interpretacao_id,
            "sessao_id": sessao_id,
            "texto_entrada": texto,
            "canal": canal,
            "operacoes": operacoes,
        },
        prefer="return=minimal",
    )


def marcar_interpretacao(interpretacao_id, aceito):
    _requisitar(
        "PATCH",
        "interpretacoes_ia",
        params={"id": f"eq.{interpretacao_id}"},
        corpo={"aceito": aceito},
        prefer="return=minimal",
    )
