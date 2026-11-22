"""
Servidor MCP do Agente 1 (Triagem N1) — FastMCP + schemas Pydantic de entrada e saída.

Expõe as 3 ferramentas de diagnóstico do Agente 1 como serviço MCP com contrato formal:
  - check_system_status       (CheckSystemStatusInput -> SystemStatus)
  - lookup_user_account       (LookupUserAccountInput -> UserAccountResult)
  - query_troubleshooting_kb  (QueryKBInput           -> KBSearchResult)

Todas são somente leitura (annotations readOnlyHint=True) e passam pelo MESMO hook
PreToolUse e pela MESMA implementação usada pelas @function_tool do agente
(agent1/tools.py, funções *_impl). Não há lógica duplicada: o MCP é outra porta de
entrada para o mesmo contrato.

Execução (a partir da raiz do repositório):
    python -m agent1.mcp.server                  # stdio (Claude Code, Agents SDK, n8n MCP Client)
    python -m agent1.mcp.server --transport streamable-http --port 8011   # HTTP em /mcp

TP4 → TP5: o arquivo antigo (agent1/mcp_server.py) importava `mcp.server.mcpserver.MCPServer`,
que não existe no SDK `mcp` instalado — o servidor nem iniciava. Foi reescrito com FastMCP.
"""
import argparse
import os
import sys
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from agent1.models import KBSearchResult, SystemStatus, UserAccountResult  # noqa: E402
from agent1.tools import (  # noqa: E402
    check_system_status_impl,
    lookup_user_account_impl,
    query_troubleshooting_kb_impl,
)

SERVER_NAME = "helpdesk-agent1-tools"
SERVER_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Schemas de ENTRADA (Pydantic). Os de SAÍDA vêm de agent1/models.py.
# Os campos são expostos como parâmetros de 1º nível da tool (sem envelope "request"):
# no teste com o Agents SDK, o LLM enviava {"user_email": ...} direto e a chamada com
# envelope falhava na validação. Cada tool reconstrói o modelo para validar a entrada.
# ---------------------------------------------------------------------------
class CheckSystemStatusInput(BaseModel):
    """Entrada de check_system_status."""
    model_config = ConfigDict(extra="forbid")
    service_name: Annotated[str, Field(
        min_length=2, max_length=40,
        description="Serviço monitorado: vpn, folha, email ou erp (aceita sinônimos como sap, outlook, openvpn).",
        examples=["vpn", "folha de pagamento"],
    )]


class LookupUserAccountInput(BaseModel):
    """Entrada de lookup_user_account."""
    model_config = ConfigDict(extra="forbid")
    user_email: Annotated[str, Field(
        min_length=6, max_length=120,
        description="E-mail corporativo terminado em @empresa.com.",
        examples=["maria.souza@empresa.com"],
    )]


class QueryKBInput(BaseModel):
    """Entrada de query_troubleshooting_kb."""
    model_config = ConfigDict(extra="forbid")
    query: Annotated[str, Field(
        min_length=2, max_length=300,
        description="Descrição curta do sintoma, em português.",
        examples=["erro 403 folha conta bloqueada"],
    )]
    top_k: Annotated[int, Field(default=2, ge=1, le=4, description="Máximo de artigos retornados.")] = 2


READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

mcp = FastMCP(
    name=SERVER_NAME,
    instructions=(
        "Ferramentas somente leitura de diagnóstico N1 de TI (Agente 1). "
        "Nenhuma ferramenta altera contas, rotas ou incidentes. Todas as chamadas passam pelo hook "
        "PreToolUse do Agente 1 (validação de domínio @empresa.com e bloqueio de injeção) e são auditadas "
        "em agent1/hooks/hook_audit.log."
    ),
)


@mcp.tool(
    name="check_system_status",
    title="Status de serviço corporativo",
    description="Consulta o status operacional (Operational, Degradado, Manutencao...) de vpn, folha, email ou erp.",
    annotations=READ_ONLY,
    structured_output=True,
)
def mcp_check_system_status(
    service_name: Annotated[str, Field(min_length=2, max_length=40,
                                       description=CheckSystemStatusInput.model_fields["service_name"].description)],
) -> SystemStatus:
    request = CheckSystemStatusInput(service_name=service_name)  # validação explícita pelo schema Pydantic
    return check_system_status_impl(request.service_name)


@mcp.tool(
    name="lookup_user_account",
    title="Conta no Active Directory",
    description="Consulta perfil, grupos e bloqueio (account_locked) de um colaborador @empresa.com no Active Directory.",
    annotations=READ_ONLY,
    structured_output=True,
)
def mcp_lookup_user_account(
    user_email: Annotated[str, Field(min_length=6, max_length=120,
                                     description=LookupUserAccountInput.model_fields["user_email"].description)],
) -> UserAccountResult:
    request = LookupUserAccountInput(user_email=user_email)
    return lookup_user_account_impl(request.user_email)


@mcp.tool(
    name="query_troubleshooting_kb",
    title="Busca na Base de Conhecimento",
    description="Busca semântica (embeddings + cosseno) nos procedimentos KB-101 a KB-104, com limiar mínimo de similaridade.",
    annotations=READ_ONLY,
    structured_output=True,
)
def mcp_query_troubleshooting_kb(
    query: Annotated[str, Field(min_length=2, max_length=300, description=QueryKBInput.model_fields["query"].description)],
    top_k: Annotated[int, Field(ge=1, le=4, description="Máximo de artigos retornados.")] = 2,
) -> KBSearchResult:
    request = QueryKBInput(query=query, top_k=top_k)
    return query_troubleshooting_kb_impl(request.query, top_k=request.top_k)


@mcp.resource("helpdesk://agent1/contract", name="agent1-tools-contract", mime_type="text/markdown")
def contract_resource() -> str:
    """Contrato formal das ferramentas (agent1/TOOLS.md)."""
    path = os.path.join(ROOT_DIR, "agent1", "TOOLS.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    parser = argparse.ArgumentParser(description="Servidor MCP do Agente 1 (Triagem N1)")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    print(f"[{SERVER_NAME} v{SERVER_VERSION}] transporte={args.transport}", file=sys.stderr)
    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
