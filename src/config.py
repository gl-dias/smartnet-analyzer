"""Leitura das variáveis de ambiente. Localmente, os valores vêm do arquivo .env."""

import os

from dotenv import load_dotenv

load_dotenv()

AMBIENTE = os.getenv("AMBIENTE", "local")
APP_USUARIO = os.getenv("APP_USUARIO", "")
APP_SENHA_HASH = os.getenv("APP_SENHA_HASH", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
PROXIES_CONFIAVEIS = int(os.getenv("PROXIES_CONFIAVEIS", "1"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
