"""
Ferramentas Python para o Agente de Helpdesk de TI.
Suporta anotações de tipo Python, chamada direta de funções e compatibilidade com o OpenAI Agents SDK.
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


# Base de dados simulada para status de sistemas corporativos
MOCK_SYSTEM_STATUS: Dict[str, Dict[str, Any]] = {
    "vpn": {
        "service_name": "VPN Corporativa",
        "status": "Degradado",
        "message": "Oscilação no gateway principal (OpenVPN). Recomendado utilizar gateway secundário BR-SA-02.",
        "last_updated": "2026-10-02 10:30:00"
    },
    "folha": {
        "service_name": "Sistema de Folha de Pagamento",
        "status": "Operational",
        "message": "Todos os serviços operando normalmente. Sem instabilidades registradas.",
        "last_updated": "2026-10-02 11:00:00"
    },
    "payroll": {
        "service_name": "Sistema de Folha de Pagamento",
        "status": "Operational",
        "message": "Todos os serviços operando normalmente. Sem instabilidades registradas.",
        "last_updated": "2026-10-02 11:00:00"
    },
    "email": {
        "service_name": "E-mail Corporativo (Exchange/Office 365)",
        "status": "Operational",
        "message": "Serviços de e-mail e calendário sincronizados.",
        "last_updated": "2026-10-02 09:15:00"
    },
    "erp": {
        "service_name": "ERP SAP Corporativo",
        "status": "Manutenção",
        "message": "Janela de manutenção programada para atualização de patches até 14h.",
        "last_updated": "2026-10-02 08:00:00"
    }
}

# Base de dados simulada de contas de usuários
MOCK_USER_ACCOUNTS: Dict[str, Dict[str, Any]] = {
    "joao.silva@empresa.com": {
        "email": "joao.silva@empresa.com",
        "name": "João Silva",
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
    Consulta o status operacional de um serviço ou sistema de TI da empresa (ex: 'vpn', 'folha', 'email', 'erp').

    Args:
        service_name: Nome do serviço para consultar o status.

    Returns:
        String em formato JSON com o status operacional e detalhes do serviço.
    """
    key = service_name.lower().strip()
    matched_key = next((k for k in MOCK_SYSTEM_STATUS if k in key or key in k), None)

    if matched_key:
        return json.dumps(MOCK_SYSTEM_STATUS[matched_key], ensure_ascii=False)

    return json.dumps({
        "service_name": service_name,
        "status": "Desconhecido",
        "message": f"Serviço '{service_name}' não encontrado na monitoria de infraestrutura.",
        "last_updated": "N/A"
    }, ensure_ascii=False)


def lookup_user_account(user_email: str) -> str:
    """
    Consulta o status da conta, permissões e grupos de acesso de um colaborador pelo e-mail corporativo.

    Args:
        user_email: E-mail corporativo do usuário.

    Returns:
        String em formato JSON com os dados da conta do usuário.
    """
    email_clean = user_email.lower().strip()
    if email_clean in MOCK_USER_ACCOUNTS:
        return json.dumps(MOCK_USER_ACCOUNTS[email_clean], ensure_ascii=False)

    return json.dumps({
        "email": user_email,
        "status": "Não Encontrado",
        "message": f"Usuário {user_email} não cadastrado no Active Directory.",
        "account_locked": False
    }, ensure_ascii=False)


def query_troubleshooting_kb(query: str) -> str:
    """
    Consulta a Base de Conhecimento interna de TI para obter instruções de resolução de problemas comuns.

    Args:
        query: Descrição do problema ou palavra-chave de busca.

    Returns:
        String com artigos ou recomendações de procedimentos de TI.
    """
    q = query.lower()
    if "403" in q or "acesso negado" in q or "permissão" in q:
        return json.dumps({
            "kb_article_id": "KB-40301",
            "title": "Erro 403 / Acesso Negado em Sistemas Internos",
            "procedure": "1. Verificar se o usuário possui o grupo no AD. 2. Caso conta bloqueada, solicitar desbloqueio N2. 3. Limpar cache do navegador ou testar em janela anônima."
        }, ensure_ascii=False)
    elif "vpn" in q or "conexão" in q or "remoto" in q:
        return json.dumps({
            "kb_article_id": "KB-80802",
            "title": "Instabilidade e Queda na VPN Corporativa",
            "procedure": "1. Alternar o gateway no cliente OpenVPN para BR-SA-02. 2. Reiniciar o serviço OpenVPN Client. 3. Caso persistence, abrir chamado N2 Infra."
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "kb_article_id": "KB-00000",
            "title": "Procedimento Geral Helpdesk N1",
            "procedure": "Coletar evidências (print do erro), reiniciar a aplicação e direcionar ao suporte do módulo específico caso persistir."
        }, ensure_ascii=False)


# Registra ferramentas no SDK do OpenAI Agents (se disponível) ou mantém as funções nativas
if HAS_AGENTS_SDK:
    tool_check_system_status = function_tool(check_system_status)
    tool_lookup_user_account = function_tool(lookup_user_account)
    tool_query_troubleshooting_kb = function_tool(query_troubleshooting_kb)
    HELP_DESK_TOOLS = [tool_check_system_status, tool_lookup_user_account, tool_query_troubleshooting_kb]
else:
    HELP_DESK_TOOLS = [check_system_status, lookup_user_account, query_troubleshooting_kb]
