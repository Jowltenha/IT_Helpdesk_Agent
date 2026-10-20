"""
Ferramentas Python externas para o Agente 1 (Triagem de TI Nivel 1).
Suporta chamadas tipadas e integracao com o OpenAI Agents SDK.
"""
import json
from typing import Dict, Any, Optional

try:
    from agents import function_tool
    HAS_AGENTS_SDK = True
except ImportError:
    HAS_AGENTS_SDK = False

    def function_tool(func):
        return func


# Base de dados simulada para status de servicos corporativos
MOCK_SYSTEM_STATUS: Dict[str, Dict[str, Any]] = {
    "vpn": {
        "service_name": "VPN Corporativa",
        "status": "Degradado",
        "message": "Oscilacao no gateway principal (OpenVPN). Recomendado utilizar gateway secundario BR-SA-02.",
        "last_updated": "2026-10-02 10:30:00"
    },
    "folha": {
        "service_name": "Sistema de Folha de Pagamento",
        "status": "Operational",
        "message": "Todos os servicos operando normalmente. Sem instabilidades registradas.",
        "last_updated": "2026-10-02 11:00:00"
    },
    "payroll": {
        "service_name": "Sistema de Folha de Pagamento",
        "status": "Operational",
        "message": "Todos os servicos operando normalmente. Sem instabilidades registradas.",
        "last_updated": "2026-10-02 11:00:00"
    },
    "email": {
        "service_name": "E-mail Corporativo (Exchange/Office 365)",
        "status": "Operational",
        "message": "Servicos de e-mail e calendario sincronizados.",
        "last_updated": "2026-10-02 09:15:00"
    },
    "erp": {
        "service_name": "ERP SAP Corporativo",
        "status": "Manutencao",
        "message": "Janela de manutencao programada para atualizacao de patches ate 14h.",
        "last_updated": "2026-10-02 08:00:00"
    }
}

# Base de dados simulada de contas de usuarios (Active Directory)
MOCK_USER_ACCOUNTS: Dict[str, Dict[str, Any]] = {
    "joao.silva@empresa.com": {
        "email": "joao.silva@empresa.com",
        "name": "Joao Silva",
        "role": "Analista Financeiro",
        "groups": ["Financeiro", "Folha_Pagamento_Leitura"],
        "account_locked": False
    },
    "maria.souza@empresa.com": {
        "email": "maria.souza@empresa.com",
        "name": "Maria Souza",
        "role": "Coordenadora de RH",
        "groups": ["RH_Gestao", "Folha_Pagamento_Admin", "VPN_Users"],
        "account_locked": True
    }
}


def check_system_status(service_name: str) -> str:
    """
    Consulta o status operacional de um servico de TI (ex: 'vpn', 'folha', 'email', 'erp').
    """
    key = service_name.lower().strip()
    matched_key = next((k for k in MOCK_SYSTEM_STATUS if k in key or key in k), None)

    if matched_key:
        return json.dumps(MOCK_SYSTEM_STATUS[matched_key], ensure_ascii=False)

    return json.dumps({
        "service_name": service_name,
        "status": "Desconhecido",
        "message": f"Servico '{service_name}' nao encontrado na monitoria de infraestrutura.",
        "last_updated": "N/A"
    }, ensure_ascii=False)


def lookup_user_account(user_email: str) -> str:
    """
    Consulta o status da conta e permissoes de um colaborador no Active Directory pelo e-mail.
    """
    email_clean = user_email.lower().strip()
    if email_clean in MOCK_USER_ACCOUNTS:
        return json.dumps(MOCK_USER_ACCOUNTS[email_clean], ensure_ascii=False)

    return json.dumps({
        "email": user_email,
        "status": "Nao Encontrado",
        "message": f"Usuario {user_email} nao cadastrado no Active Directory.",
        "account_locked": False
    }, ensure_ascii=False)


def query_troubleshooting_kb(query: str) -> str:
    """
    Consulta a Base de Conhecimento interna de TI para obter procedimentos recomendados.
    """
    q = query.lower()
    if "403" in q or "acesso negado" in q or "permissao" in q:
        return json.dumps({
            "kb_article_id": "KB-40301",
            "title": "Erro 403 / Acesso Negado em Sistemas Internos",
            "procedure": "1. Verificar se o usuario possui o grupo no AD. 2. Caso conta bloqueada, solicitar desbloqueio N2. 3. Limpar cache do navegador."
        }, ensure_ascii=False)
    elif "vpn" in q or "conexao" in q or "remoto" in q:
        return json.dumps({
            "kb_article_id": "KB-80802",
            "title": "Instabilidade e Queda na VPN Corporativa",
            "procedure": "1. Alternar gateway OpenVPN para BR-SA-02. 2. Reiniciar servico OpenVPN Client. 3. Caso persistencia, escalar para N2."
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "kb_article_id": "KB-00000",
            "title": "Procedimento Geral Helpdesk N1",
            "procedure": "Coletar evidencias, reiniciar a aplicacao e direcionar ao suporte do modulo se o erro persistir."
        }, ensure_ascii=False)


if HAS_AGENTS_SDK:
    tool_check_system_status = function_tool(check_system_status)
    tool_lookup_user_account = function_tool(lookup_user_account)
    tool_query_troubleshooting_kb = function_tool(query_troubleshooting_kb)
    HELP_DESK_TOOLS = [tool_check_system_status, tool_lookup_user_account, tool_query_troubleshooting_kb]
else:
    HELP_DESK_TOOLS = [check_system_status, lookup_user_account, query_troubleshooting_kb]
