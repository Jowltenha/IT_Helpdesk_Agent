"""
Autenticação por token compartilhado (header X-API-Key) entre o n8n e o Agente 1.

O valor vem da variável de ambiente AGENT1_API_TOKEN (arquivo .env, fora do git).
No n8n, o mesmo valor fica numa credencial criptografada do tipo Header Auth
("Helpdesk Agent 1 - X-API-Key"), nunca dentro do JSON do workflow.
Se a variável não estiver definida, a API fica aberta (modo de desenvolvimento) e o
/health informa "auth_enabled": false.
"""
import hmac
import os
from typing import Callable, Optional

from dotenv import load_dotenv
from fastapi import Header, HTTPException, status

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

API_TOKEN: Optional[str] = os.getenv("AGENT1_API_TOKEN") or None


def make_api_key_dependency(get_token: Callable[[], Optional[str]]):
    """Cria a dependência FastAPI; o token é lido a cada requisição (permite rotação e testes)."""

    def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
        token = get_token()
        if token is None:
            return
        if not x_api_key or not hmac.compare_digest(x_api_key, token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key ausente ou inválida.")

    return require_api_key
