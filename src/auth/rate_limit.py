"""Limite de requisições em memória, com janela deslizante."""

import threading
import time

from src import config

LIMPEZA_ACIMA_DE_CHAVES = 10000


class LimitadorTaxa:
    """Permite no máximo `maximo` eventos por chave a cada `janela_segundos`.

    Como fica em memória, a contagem zera quando o servidor reinicia e não é
    compartilhada entre processos, o que basta para uma única instância.
    """

    def __init__(self, maximo, janela_segundos, relogio=time.monotonic):
        self.maximo = maximo
        self.janela_segundos = janela_segundos
        self._relogio = relogio
        self._eventos = {}
        self._trava = threading.Lock()

    def permitir(self, chave):
        """Registra o evento e devolve True, ou devolve False se o limite já foi atingido."""
        with self._trava:
            agora = self._relogio()
            if len(self._eventos) > LIMPEZA_ACIMA_DE_CHAVES:
                self._remover_expirados(agora)
            recentes = [t for t in self._eventos.get(chave, []) if agora - t < self.janela_segundos]
            permitido = len(recentes) < self.maximo
            if permitido:
                recentes.append(agora)
            self._eventos[chave] = recentes
            return permitido

    def limpar(self, chave=None):
        """Zera a contagem de uma chave ou, sem argumento, de todas."""
        with self._trava:
            if chave is None:
                self._eventos.clear()
            else:
                self._eventos.pop(chave, None)

    def _remover_expirados(self, agora):
        self._eventos = {
            chave: eventos
            for chave, eventos in self._eventos.items()
            if eventos and agora - eventos[-1] < self.janela_segundos
        }


def ip_cliente(request):
    """IP de origem da requisição.

    Em produção, o Render fica na frente da aplicação, então o IP real vem em
    X-Forwarded-For. Localmente esse cabeçalho é ignorado, pois qualquer cliente
    poderia enviá-lo para escapar do limite.
    """
    if config.AMBIENTE == "producao":
        encaminhado = request.headers.get("x-forwarded-for", "")
        primeiro = encaminhado.split(",")[0].strip()
        if primeiro:
            return primeiro
    return request.client.host if request.client else "desconhecido"
