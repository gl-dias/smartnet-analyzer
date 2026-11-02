# SmartNet Analyzer

README em construção: a versão final entra na última fase do projeto.

## Segurança

- **Limitação da sessão:** a sessão fica apenas no cookie assinado, sem registro no servidor. O logout apaga o cookie do navegador, mas uma cópia roubada continua válida até expirar (8 horas após o login). Trocar a `SECRET_KEY` invalida todas as sessões de uma vez.
- **IP de origem nos limites de login:** em produção, o IP vem de `X-Forwarded-For`, contado a partir do fim da lista, porque cada proxy acrescenta um IP ao final e o início é controlado pelo cliente. A variável `PROXIES_CONFIAVEIS` define a posição: `1` usa o último IP (padrão), `2` usa o penúltimo e `0` ignora o cabeçalho. Localmente, o cabeçalho é sempre ignorado.
