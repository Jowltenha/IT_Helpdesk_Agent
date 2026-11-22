"""
Inicializador do Chainlit compatível com Python 3.14.

Por que este arquivo existe:
    O CLI do Chainlit chama `nest_asyncio.apply()` ao iniciar. No Python 3.14 isso
    quebra a detecção do event loop feita pelo anyio/sniffio, e toda requisição
    falha com `anyio.NoEventLoopError: Not currently running on any asynchronous
    event loop`. O nest_asyncio não é necessário para rodar o servidor, então ele
    é desativado aqui antes de carregar o CLI do Chainlit.

Uso (a partir da raiz do projeto, com o .venv ativo):
    python chatbot/run_chainlit.py run chatbot/app.py -w
"""
import sys

import nest_asyncio

nest_asyncio.apply = lambda *args, **kwargs: None  # desativa o patch incompatível com Python 3.14

from chainlit.cli import cli  # noqa: E402  (precisa vir depois do patch acima)

if __name__ == "__main__":
    sys.exit(cli())
