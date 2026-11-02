"""Configuração dos testes: credenciais próprias, independentes de qualquer .env local."""

import os

import bcrypt
import pytest

USUARIO_TESTE = "avaliador"
SENHA_TESTE = "senha-de-teste"

# Definidas antes de importar a aplicação. O load_dotenv não sobrescreve variáveis existentes.
os.environ.update(
    {
        "AMBIENTE": "local",
        "APP_USUARIO": USUARIO_TESTE,
        "APP_SENHA_HASH": bcrypt.hashpw(SENHA_TESTE.encode(), bcrypt.gensalt(rounds=4)).decode(),
        "SECRET_KEY": "chave-usada-somente-nos-testes",
    }
)

from src.auth import sessao  # noqa: E402


@pytest.fixture(autouse=True)
def zerar_limites():
    sessao.limitador_login_ip.limpar()
    sessao.limitador_login_global.limpar()
