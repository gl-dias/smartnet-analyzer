"""Login com conta única, sessão em cookie assinado e encerramento da sessão."""

import hmac
import logging
import secrets
import time
import uuid
from pathlib import Path

import bcrypt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from src import config
from src.auth.rate_limit import LimitadorTaxa, ip_cliente

PASTA_PUBLICA = Path(__file__).resolve().parent.parent.parent / "public"

DURACAO_SESSAO_SEGUNDOS = 8 * 60 * 60
JANELA_LOGIN_SEGUNDOS = 15 * 60
MENSAGEM_CREDENCIAIS = "Usuário ou senha inválidos"
MENSAGEM_BLOQUEIO = "Muitas tentativas, aguarde alguns minutos"

logger = logging.getLogger(__name__)
roteador = APIRouter()

limitador_login_ip = LimitadorTaxa(5, JANELA_LOGIN_SEGUNDOS)
# Teto para todos os IPs juntos: mesmo que o IP de origem seja falsificado ou venha de
# muitas máquinas, não é possível testar senhas sem limite.
limitador_login_global = LimitadorTaxa(50, JANELA_LOGIN_SEGUNDOS)


class LoginEntrada(BaseModel):
    usuario: str
    senha: str


def opcoes_cookie(ambiente):
    """Opções do SessionMiddleware. O cookie é sempre HttpOnly; Secure só em produção."""
    return {
        "session_cookie": "smartnet_sessao",
        "max_age": DURACAO_SESSAO_SEGUNDOS,
        "same_site": "lax",
        "https_only": ambiente == "producao",
    }


def chave_secreta(ambiente, valor):
    """Chave que assina o cookie. Sem ela, produção não sobe e local usa uma chave temporária."""
    if valor:
        return valor
    if ambiente == "producao":
        raise RuntimeError("Defina a variável de ambiente SECRET_KEY.")
    logger.warning("SECRET_KEY não definida: as sessões serão perdidas ao reiniciar o servidor.")
    return secrets.token_urlsafe(48)


def _agora():
    return time.time()


def _credenciais_validas(usuario, senha):
    """Compara usuário e senha sempre por inteiro, para não revelar qual dos dois errou."""
    try:
        usuario_ok = hmac.compare_digest(usuario.encode(), config.APP_USUARIO.encode())
        senha_ok = bcrypt.checkpw(senha.encode(), config.APP_SENHA_HASH.encode())
    except ValueError:
        # Senha acima de 72 bytes, caractere inválido ou hash ausente/malformado.
        return False
    return bool(config.APP_USUARIO) and usuario_ok and senha_ok


def sessao_valida(request):
    """Confere a sessão. As 8 horas contam do login, mesmo com o cookie sendo renovado a cada resposta."""
    sessao = request.session
    usuario = sessao.get("usuario")
    if not usuario or usuario != config.APP_USUARIO:
        return False
    return _agora() - sessao.get("inicio", 0) <= DURACAO_SESSAO_SEGUNDOS


@roteador.get("/login", include_in_schema=False)
def pagina_login(request: Request):
    if sessao_valida(request):
        return RedirectResponse("/", status_code=303)
    return FileResponse(PASTA_PUBLICA / "login.html")


@roteador.post("/login")
def login(dados: LoginEntrada, request: Request):
    ip = ip_cliente(request)
    if not (limitador_login_ip.permitir(ip) and limitador_login_global.permitir("todos")):
        raise HTTPException(status_code=429, detail=MENSAGEM_BLOQUEIO)
    if not _credenciais_validas(dados.usuario, dados.senha):
        raise HTTPException(status_code=401, detail=MENSAGEM_CREDENCIAIS)
    limitador_login_ip.limpar(ip)
    request.session.clear()
    request.session.update(
        {"usuario": dados.usuario, "id": str(uuid.uuid4()), "inicio": _agora()}
    )
    return {"ok": True}


@roteador.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@roteador.post("/api/sessao/finalizar")
def finalizar_sessao(request: Request):
    request.session.clear()
    return {"ok": True}
