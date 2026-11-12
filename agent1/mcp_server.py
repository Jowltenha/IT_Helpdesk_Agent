"""
Servidor MCP (Model Context Protocol) para o Agente 1 de Helpdesk.
Atende ao Requisito 6 do Projeto (Slide 8):
"Servidor MCP deve expor as ferramentas de ao menos um dos agentes"

Expõe via protocolo padrão MCP as ferramentas de diagnóstico:
 1. check_system_status
 2. lookup_user_account
 3. query_troubleshooting_kb
"""
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.mcpserver import MCPServer
from agent1.tools import check_system_status, lookup_user_account, query_troubleshooting_kb

# Inicializa o servidor MCP
mcp_server = MCPServer(
    name="helpdesk-agent1-tools",
    title="IT Helpdesk Agent 1 MCP Server",
    description="Servidor MCP que disponibiliza ferramentas de diagnóstico N1 de TI para orquestradores e agentes externos"
)


@mcp_server.tool(
    name="check_system_status",
    description="Consulta o status operacional de um serviço de TI corporativo (vpn, folha, email, erp)."
)
def mcp_check_system_status(service_name: str) -> str:
    """Consulta o status operacional de um serviço de infraestrutura corporativa."""
    return check_system_status(service_name)


@mcp_server.tool(
    name="lookup_user_account",
    description="Consulta o perfil, grupos e status de bloqueio de conta de um colaborador no Active Directory."
)
def mcp_lookup_user_account(user_email: str) -> str:
    """Consulta conta e permissões de um usuário corporativo no Active Directory."""
    return lookup_user_account(user_email)


@mcp_server.tool(
    name="query_troubleshooting_kb",
    description="Consulta artigos e procedimentos operacionais da Base de Conhecimento N1 de TI."
)
def mcp_query_troubleshooting_kb(query: str) -> str:
    """Recupera procedimentos de suporte da Base de Conhecimento interna."""
    return query_troubleshooting_kb(query)


def main():
    """Inicia o servidor MCP usando transporte stdio (padrão Claude Desktop / n8n MCP Client)."""
    print("Iniciando Servidor MCP do Agente 1 (Transport: stdio)...", file=sys.stderr)
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
