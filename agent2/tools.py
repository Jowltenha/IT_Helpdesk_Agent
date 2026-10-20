"""
Ferramentas Python de Auto-Remediacao e Despacho N2 para o Agente 2.
Permite executar acoes tecnicas reais/simuladas com trilha de auditoria e tipagem estrita.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    from agents import function_tool
    HAS_AGENTS_SDK = True
except ImportError:
    HAS_AGENTS_SDK = False

    def function_tool(func):
        return func


# Estado simulado de diretorio ativo (Active Directory) compartilhado no escopo de execucao
MOCK_AD_ACCOUNTS: Dict[str, Dict[str, Any]] = {
    "maria.souza@empresa.com": {
        "email": "maria.souza@empresa.com",
        "name": "Maria Souza",
        "account_locked": True,
        "failed_attempts": 5,
        "last_locked_time": "2026-10-19 13:45:00"
    },
    "joao.silva@empresa.com": {
        "email": "joao.silva@empresa.com",
        "name": "Joao Silva",
        "account_locked": False,
        "failed_attempts": 0,
        "last_locked_time": None
    }
}

# Registro de incidentes no sistema ITSM corporativo
MOCK_ITSM_TICKETS: Dict[str, Dict[str, Any]] = {}


def unlock_user_account(user_email: str, reason: str = "Solicitacao automatizada via Helpdesk") -> str:
    """
    Executa o desbloqueio de seguranca de uma conta no Active Directory corporativo.

    Args:
        user_email: E-mail da conta corporativa a ser desbloqueada.
        reason: Motivo ou identificador de auditoria para o desbloqueio.

    Returns:
        String em formato JSON com o resultado da operacao e token de auditoria.
    """
    clean_email = user_email.lower().strip()
    audit_code = f"AUDIT-AD-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    if clean_email in MOCK_AD_ACCOUNTS:
        account = MOCK_AD_ACCOUNTS[clean_email]
        was_locked = account["account_locked"]
        account["account_locked"] = False
        account["failed_attempts"] = 0
        account["unlocked_at"] = timestamp

        return json.dumps({
            "operation": "UNLOCK_USER_ACCOUNT",
            "email": clean_email,
            "status": "SUCCESS",
            "previous_state": "LOCKED" if was_locked else "ALREADY_ACTIVE",
            "current_state": "ACTIVE",
            "audit_code": audit_code,
            "message": f"Conta de {account['name']} desbloqueada com sucesso no Active Directory.",
            "timestamp": timestamp
        }, ensure_ascii=False)

    # Se a conta nao constava no mock, provisiona desbloqueio de contingencia
    return json.dumps({
        "operation": "UNLOCK_USER_ACCOUNT",
        "email": clean_email,
        "status": "SUCCESS",
        "previous_state": "UNKNOWN",
        "current_state": "ACTIVE",
        "audit_code": audit_code,
        "message": f"Comando de desbloqueio propagado no dominio AD para {clean_email}.",
        "timestamp": timestamp
    }, ensure_ascii=False)


def configure_vpn_failover_route(user_email: str, gateway: str = "BR-SA-02") -> str:
    """
    Provisiona rota de redundancia e configura chave de contingencia para a VPN corporativa.

    Args:
        user_email: E-mail do usuario afetado pela instabilidade.
        gateway: Identificador do gateway de contingencia operacional.

    Returns:
        String em formato JSON com o perfil e chave temporaria gerados.
    """
    session_token = f"VPN-FAILOVER-{uuid.uuid4().hex[:10].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    return json.dumps({
        "operation": "CONFIGURE_VPN_FAILOVER_ROUTE",
        "email": user_email,
        "target_gateway": gateway,
        "session_token": session_token,
        "status": "SUCCESS",
        "dns_servers": ["10.0.0.10", "10.0.0.11"],
        "message": f"Rota de contingencia atribuida para o gateway secundario {gateway}.",
        "timestamp": timestamp
    }, ensure_ascii=False)


def dispatch_sla_incident(ticket_id: str, severity: str, team: str, justification: str) -> str:
    """
    Registra um incidente de escalonamento no sistema ITSM corporativo e calcula a meta de SLA.

    Args:
        ticket_id: Identificador do chamado original.
        severity: Nivel de severidade (Critica, Alta, Media, Baixa).
        team: Equipe tecnica responsavel (ex: 'N2 Infraestrutura', 'Suporte Presencial N2').
        justification: Justificativa tecnica para o escalonamento.

    Returns:
        String JSON com o registro do incidente, plantonista alocado e prazo de SLA em minutos.
    """
    sla_map = {
        "critica": 30,
        "alta": 120,
        "media": 480,
        "baixa": 1440
    }
    sla_minutes = sla_map.get(severity.lower(), 240)
    incident_number = f"INC-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    ticket_record = {
        "incident_number": incident_number,
        "original_ticket_id": ticket_id,
        "assigned_team": team,
        "severity": severity,
        "sla_target_minutes": sla_minutes,
        "on_call_engineer": "Plantao_N2_Engenharia",
        "status": "DISPATCHED",
        "justification": justification,
        "dispatched_at": timestamp
    }
    MOCK_ITSM_TICKETS[incident_number] = ticket_record

    return json.dumps(ticket_record, ensure_ascii=False)


if HAS_AGENTS_SDK:
    tool_unlock_user_account = function_tool(unlock_user_account)
    tool_configure_vpn_failover_route = function_tool(configure_vpn_failover_route)
    tool_dispatch_sla_incident = function_tool(dispatch_sla_incident)
    REMEDIATION_TOOLS = [tool_unlock_user_account, tool_configure_vpn_failover_route, tool_dispatch_sla_incident]
else:
    REMEDIATION_TOOLS = [unlock_user_account, configure_vpn_failover_route, dispatch_sla_incident]
