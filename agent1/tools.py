"""
Ferramentas Python externas do Agente 1 (Triagem de TI Nível 1).

Cada ferramenta:
  1. passa pelo hook PreToolUse (hooks/pre_tool_validator.py), que valida e sanitiza os argumentos;
  2. devolve JSON validado por um modelo Pydantic (agent1/models.py), o mesmo contrato usado
     pelo servidor MCP (agent1/mcp/server.py).

As funções `*_impl` retornam o modelo Pydantic (usadas pelo MCP); as funções públicas
retornam a string JSON (usadas como @function_tool pelo Agents SDK).

TP5 — refinamentos baseados nos testes:
  * check_system_status: o modelo pediu 'infraestrutura' no caso de hardware e recebeu
    "Bloqueado". Agora a resolução usa aliases (sap→erp, outlook→email, openvpn→vpn,
    "folha de pagamento"→folha...) e, quando o serviço não é monitorado, devolve a lista
    de serviços válidos para o modelo se corrigir sem perder uma chamada.
  * lookup_user_account: e-mail com ponto final ("maria.souza@empresa.com.") chegou ao
    Agente 2 e virou um "desbloqueio de contingência" de conta inexistente. A ferramenta
    agora normaliza o e-mail e devolve `found` explícito; quando o hook nega, `account_locked`
    é None (antes era False, o que dava a entender que a conta estava saudável).
  * query_troubleshooting_kb: tinha artigos próprios (KB-40301, KB-80802) que não existiam
    no RAG, e o modelo passou a citar IDs inconsistentes. Agora consulta o mesmo índice
    vetorial do RAG (fonte única KB-101..KB-104), com limiar de similaridade.
"""
import json
import unicodedata
from typing import Any, Dict, Optional

from agent1.hooks.pre_tool_validator import pre_tool_use_hook
from agent1.models import (
    KBSearchResult,
    KnowledgeArticle,
    SystemStatus,
    UserAccountResult,
    normalize_corporate_email,
)
from agent1.rag import RAGUnavailableError, get_shared_rag

try:
    from agents import function_tool
    HAS_AGENTS_SDK = True
except ImportError:  # permite usar as tools (ex.: no MCP) sem o SDK instalado
    HAS_AGENTS_SDK = False

# ---------------------------------------------------------------------------
# Dados simulados de infraestrutura (o ambiente acadêmico não tem AD/monitoria reais)
# ---------------------------------------------------------------------------
MOCK_SYSTEM_STATUS: Dict[str, Dict[str, Any]] = {
    "vpn": {
        "service_name": "VPN Corporativa",
        "status": "Degradado",
        "message": "Oscilacao no gateway principal (OpenVPN). Recomendado utilizar gateway secundario BR-SA-02.",
        "last_updated": "2026-10-02 10:30:00",
    },
    "folha": {
        "service_name": "Sistema de Folha de Pagamento",
        "status": "Operational",
        "message": "Todos os servicos operando normalmente. Sem instabilidades registradas.",
        "last_updated": "2026-10-02 11:00:00",
    },
    "email": {
        "service_name": "E-mail Corporativo (Exchange/Office 365)",
        "status": "Operational",
        "message": "Servicos de e-mail e calendario sincronizados.",
        "last_updated": "2026-10-02 09:15:00",
    },
    "erp": {
        "service_name": "ERP SAP Corporativo",
        "status": "Manutencao",
        "message": "Janela de manutencao programada para atualizacao de patches ate 14h.",
        "last_updated": "2026-10-02 08:00:00",
    },
}

# Nomes alternativos que o modelo e os usuários usam para os serviços monitorados
SERVICE_ALIASES: Dict[str, str] = {
    "vpn": "vpn", "openvpn": "vpn", "gateway": "vpn", "acesso remoto": "vpn",
    "folha": "folha", "folha de pagamento": "folha", "payroll": "folha", "rh": "folha",
    "email": "email", "e-mail": "email", "outlook": "email", "exchange": "email", "office 365": "email", "office365": "email",
    "erp": "erp", "sap": "erp", "erp sap": "erp",
}

MOCK_USER_ACCOUNTS: Dict[str, Dict[str, Any]] = {
    "joao.silva@empresa.com": {
        "name": "Joao Silva",
        "role": "Analista Financeiro",
        "groups": ["Financeiro", "Folha_Pagamento_Leitura", "VPN_Users"],
        "account_locked": False,
    },
    "maria.souza@empresa.com": {
        "name": "Maria Souza",
        "role": "Coordenadora de RH",
        "groups": ["RH_Gestao", "Folha_Pagamento_Admin", "VPN_Users"],
        "account_locked": True,
    },
    "carlos.lima@empresa.com": {
        "name": "Carlos Lima",
        "role": "Analista de Logistica",
        "groups": ["Logistica", "ERP_Usuarios"],
        "account_locked": False,
    },
}


def _fold(text: str) -> str:
    """Minúsculas e sem acentos, para comparação tolerante."""
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower().strip()


def resolve_service_key(service_name: str) -> Optional[str]:
    """Resolve o nome livre do serviço para uma chave monitorada (ou None)."""
    name = _fold(service_name)
    if name in SERVICE_ALIASES:
        return SERVICE_ALIASES[name]
    # alias como palavra contida (ex.: "sistema de folha de pagamento" -> folha)
    for alias in sorted(SERVICE_ALIASES, key=len, reverse=True):
        if alias in name:
            return SERVICE_ALIASES[alias]
    return None


# ---------------------------------------------------------------------------
# Implementações tipadas (contrato Pydantic) — reutilizadas pelo servidor MCP
# ---------------------------------------------------------------------------
def check_system_status_impl(service_name: str) -> SystemStatus:
    allowed, reason, args = pre_tool_use_hook("check_system_status", {"service_name": service_name})
    if not allowed:
        return SystemStatus(
            service_name=service_name, status="NEGADO_PELO_HOOK", message=reason, last_updated="N/A",
            monitored_services=sorted(MOCK_SYSTEM_STATUS),
        )
    key = resolve_service_key(args["service_name"])
    if key is None:
        return SystemStatus(
            service_name=args["service_name"], status="Desconhecido",
            message="Servico nao monitorado. Use uma das chaves em monitored_services ou siga sem esta consulta.",
            last_updated="N/A", monitored_services=sorted(MOCK_SYSTEM_STATUS),
        )
    return SystemStatus(service_key=key, **MOCK_SYSTEM_STATUS[key])


def lookup_user_account_impl(user_email: str) -> UserAccountResult:
    allowed, reason, args = pre_tool_use_hook("lookup_user_account", {"user_email": user_email})
    if not allowed:
        return UserAccountResult(
            email=str(user_email), found=False, status="NEGADO_PELO_HOOK", account_locked=None,
            message=f"{reason} Peça ao colaborador o e-mail corporativo; nao assuma o estado da conta.",
        )
    email = normalize_corporate_email(args["user_email"]) or args["user_email"]
    account = MOCK_USER_ACCOUNTS.get(email)
    if account is None:
        return UserAccountResult(
            email=email, found=False, status="NAO_ENCONTRADO", account_locked=None,
            message="Conta inexistente no Active Directory. Encaminhar para RH/Onboarding; nao solicitar desbloqueio.",
        )
    return UserAccountResult(email=email, found=True, status="ENCONTRADO", message="Conta localizada.", **account)


def query_troubleshooting_kb_impl(query: str, top_k: int = 2) -> KBSearchResult:
    rag = get_shared_rag()
    allowed, reason, args = pre_tool_use_hook("query_troubleshooting_kb", {"query": query})
    if not allowed:
        return KBSearchResult(query=str(query), status="NEGADO_PELO_HOOK", min_similarity=rag.min_similarity, message=reason)
    clean_query = args["query"]
    try:
        results = rag.retrieve(clean_query, top_k=max(1, min(int(top_k), 4)))
    except RAGUnavailableError as exc:
        return KBSearchResult(query=clean_query, status="KB_INDISPONIVEL", min_similarity=rag.min_similarity, message=str(exc))
    articles = [
        KnowledgeArticle(article_id=d["id"], title=d["title"], category=d["category"], solution=d["content"], relevance_score=s)
        for d, s in results
    ]
    return KBSearchResult(
        query=clean_query,
        status="ENCONTRADO" if articles else "SEM_ARTIGO_RELEVANTE",
        articles=articles,
        min_similarity=rag.min_similarity,
        message="" if articles else "Nenhum artigo relevante; nao cite IDs de artigo no laudo.",
    )


# ---------------------------------------------------------------------------
# Wrappers públicos (string JSON) — expostos ao modelo via @function_tool
# ---------------------------------------------------------------------------
def check_system_status(service_name: str) -> str:
    """
    Consulta o status operacional de um servico corporativo monitorado.

    Args:
        service_name: Nome do servico. Chaves monitoradas: vpn, folha, email, erp
            (aceita sinonimos como 'sap', 'outlook', 'folha de pagamento', 'openvpn').
            Nao use para hardware/estacao de trabalho: esses itens nao sao monitorados.
    """
    return check_system_status_impl(service_name).model_dump_json()


def lookup_user_account(user_email: str) -> str:
    """
    Consulta perfil, grupos e bloqueio (account_locked) de um colaborador no Active Directory.

    Args:
        user_email: E-mail corporativo terminado em @empresa.com, exatamente como informado no chamado.
            Nunca invente um e-mail; se o chamado nao tiver e-mail corporativo, nao chame esta ferramenta.
    """
    return lookup_user_account_impl(user_email).model_dump_json()


def query_troubleshooting_kb(query: str) -> str:
    """
    Busca semantica (embeddings + cosseno) nos procedimentos da Base de Conhecimento (KB-101 a KB-104).

    Args:
        query: Descricao curta do sintoma em portugues (ex.: 'erro 403 folha conta bloqueada').
    """
    return query_troubleshooting_kb_impl(query).model_dump_json()


if HAS_AGENTS_SDK:
    HELP_DESK_TOOLS = [
        function_tool(check_system_status),
        function_tool(lookup_user_account),
        function_tool(query_troubleshooting_kb),
    ]
else:
    HELP_DESK_TOOLS = [check_system_status, lookup_user_account, query_troubleshooting_kb]

__all__ = [
    "check_system_status", "lookup_user_account", "query_troubleshooting_kb",
    "check_system_status_impl", "lookup_user_account_impl", "query_troubleshooting_kb_impl",
    "HELP_DESK_TOOLS", "resolve_service_key", "json",
]
