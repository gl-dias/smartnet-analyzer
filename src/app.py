"""Aplicação FastAPI: middlewares, rotas e arquivos estáticos."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from src import config
from src.api import rotas_algoritmos, rotas_grafo, rotas_ia
from src.auth import sessao
from src.core.grafo import ErroGrafo

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

PASTA_PUBLICA = Path(__file__).resolve().parent.parent / "public"

# Tudo exige sessão, exceto estes caminhos exatos. Rotas novas já nascem protegidas.
CAMINHOS_PUBLICOS = frozenset({"/login", "/logout", "/saude", "/css/estilos.css", "/js/login.js"})

MENSAGENS_VALIDACAO = {
    "missing": "campo obrigatório",
    "string_type": "deve ser um texto",
    "int_type": "deve ser um número inteiro",
    "float_type": "deve ser um número",
    "bool_type": "deve ser verdadeiro ou falso",
    "list_type": "deve ser uma lista",
    "model_type": "deve ser um objeto",
    "model_attributes_type": "deve ser um objeto",
    "too_long": "excede o tamanho máximo permitido",
    "literal_error": "valor não permitido",
    "json_invalid": "JSON inválido",
}

MENSAGENS_HTTP = {404: "Recurso não encontrado.", 405: "Método não permitido."}

app = FastAPI(title="SmartNet Analyzer", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def exigir_sessao(request: Request, chamar_proximo):
    if request.url.path in CAMINHOS_PUBLICOS or sessao.sessao_valida(request):
        return await chamar_proximo(request)
    request.session.clear()
    if request.url.path == "/":
        return RedirectResponse("/login", status_code=303)
    return JSONResponse(
        status_code=401, content={"erro": "Sessão expirada. Faça login novamente."}
    )


# Adicionado por último para ficar por fora de exigir_sessao e preparar request.session antes dele.
app.add_middleware(
    SessionMiddleware,
    secret_key=sessao.chave_secreta(config.AMBIENTE, config.SECRET_KEY),
    **sessao.opcoes_cookie(config.AMBIENTE),
)


@app.exception_handler(ErroGrafo)
async def tratar_erro_grafo(_: Request, erro: ErroGrafo):
    return JSONResponse(status_code=422, content={"erro": str(erro)})


@app.exception_handler(RequestValidationError)
async def tratar_erro_validacao(_: Request, erro: RequestValidationError):
    problema = erro.errors()[0]
    tipo = problema["type"]
    # Uniões de tipos geram um sufixo com o tipo testado, como arestas.0.peso.int.
    campos = [str(p) for p in problema["loc"] if p != "body"]
    while campos and campos[-1] in ("str", "int", "float"):
        campos.pop()
    mensagem = MENSAGENS_VALIDACAO.get(tipo, "valor inválido")
    prefixo = f"Campo {'.'.join(campos)}: " if campos else ""
    return JSONResponse(status_code=422, content={"erro": f"{prefixo}{mensagem}."})


@app.exception_handler(HTTPException)
async def tratar_erro_http(_: Request, erro: HTTPException):
    # O detalhe padrão do framework vem em inglês; os das nossas rotas já estão em português.
    padrao = erro.detail in ("Not Found", "Method Not Allowed")
    mensagem = MENSAGENS_HTTP.get(erro.status_code, erro.detail) if padrao else erro.detail
    return JSONResponse(status_code=erro.status_code, content={"erro": mensagem})


app.include_router(sessao.roteador)
app.include_router(rotas_grafo.roteador)
app.include_router(rotas_algoritmos.roteador)
app.include_router(rotas_ia.roteador)


@app.get("/saude")
def saude():
    return {"status": "ok"}


@app.get("/")
def pagina_principal():
    return FileResponse(PASTA_PUBLICA / "index.html")


app.mount("/css", StaticFiles(directory=PASTA_PUBLICA / "css"), name="css")
app.mount("/js", StaticFiles(directory=PASTA_PUBLICA / "js"), name="js")
