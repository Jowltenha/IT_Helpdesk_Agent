"""
Ferramentas Python de Auto-Remediação e Despacho N2 do Agente 2.
Cada ação passa pelo hook PostToolUse (hooks/post_tool_auditor.py), que injeta o
compliance_hash SHA-256 e grava a trilha em hooks/security_audit.log.

TP5 — refinamentos baseados nos testes (tests/results/baseline_pre_tp5.json):
  * unlock_user_account: no TP4, quando a conta NÃO existia no AD simulado, a ferramenta
    devolvia SUCCESS ("desbloqueio de contingência") — inclusive para 'atacante@gmail.com'
    e 'maria.souza@empresa.com.' (com ponto final). Agora:
      - valida domínio @empresa.com (defesa em profundidade, além do contrato de entrada);
      - conta inexistente → status FAILED/NOT_FOUND, sem alterar nada;
      - conta já ativa → SKIPPED (idempotente, não gera "desbloqueio" falso).
  * dispatch_sla_incident: 'Média' (com acento) caía no default de 240 min, valor fora da
    matriz oficial. Agora a severidade é normalizada (sem acento) e um valor inválido é
    recusado, em vez de gerar SLA inventado. A matriz é a mesma do sub-workflow do n8n.
  * configure_vpn_failover_route: aceita somente gateways da lista aprovada (BR-SA-02) e
    (rodada 2) exige conta existente no AD; sempre emite audit_code e registra ticket_id.
  * dispatch_sla_incident (rodada 2): idempotente por ticket_id (reenvio não duplica INC).
"""
import json
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from agent2.hooks.post_tool_auditor import post_tool_use_hook

try:
    from agents import function_tool
    HAS_AGENTS_SDK = True
except ImportError:
    HAS_AGENTS_SDK = False

CORPORATE_DOMAIN = "@empresa.com"
APPROVED_VPN_GATEWAYS = {"BR-SA-02"}
SLA_MATRIX_MINUTES: Dict[str, int] = {"critica": 30, "alta": 120, "media": 480, "baixa": 1440}

# Estado simulado do Active Directory (ambiente acadêmico)
MOCK_AD_ACCOUNTS: Dict[str, Dict[str, Any]] = {
    "maria.souza@empresa.com": {"name": "Maria Souza", "account_locked": True, "failed_attempts": 5,
                                "last_locked_time": "2026-10-19 13:45:00"},
    "joao.silva@empresa.com": {"name": "Joao Silva", "account_locked": False, "failed_attempts": 0,
                               "last_locked_time": None},
    "carlos.lima@empresa.com": {"name": "Carlos Lima", "account_locked": False, "failed_attempts": 0,
                                "last_locked_time": None},
}

MOCK_ITSM_TICKETS: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_email(email: str) -> str:
    return (email or "").strip().lower().rstrip(".,;:")


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text or "") if unicodedata.category(c) != "Mn").lower().strip()


def reset_mock_state() -> None:
    """Restaura o AD simulado ao estado inicial (usado pelos testes regressivos)."""
    MOCK_AD_ACCOUNTS["maria.souza@empresa.com"].update(account_locked=True, failed_attempts=5)
    MOCK_AD_ACCOUNTS["maria.souza@empresa.com"].pop("unlocked_at", None)
    MOCK_ITSM_TICKETS.clear()


def unlock_user_account(user_email: str, reason: str = "Solicitacao automatizada via Helpdesk") -> str:
    """
    Desbloqueia uma conta corporativa existente no Active Directory e zera as falhas de login.

    Args:
        user_email: E-mail corporativo (@empresa.com) da conta.
        reason: Motivo / ticket de auditoria.
    """
    email = _norm_email(user_email)
    base = {"operation": "UNLOCK_USER_ACCOUNT", "email": email, "timestamp": _now(),
            "audit_code": f"AUDIT-AD-{uuid.uuid4().hex[:8].upper()}"}

    if not email.endswith(CORPORATE_DOMAIN):
        res = {**base, "status": "BLOCKED", "previous_state": "N/A", "current_state": "N/A",
               "message": f"Recusado: '{email}' nao pertence ao dominio corporativo {CORPORATE_DOMAIN}."}
    elif email not in MOCK_AD_ACCOUNTS:
        res = {**base, "status": "FAILED", "previous_state": "NOT_FOUND", "current_state": "NOT_FOUND",
               "message": f"Conta {email} nao existe no Active Directory. Nenhuma alteracao realizada."}
    else:
        account = MOCK_AD_ACCOUNTS[email]
        if not account["account_locked"]:
            res = {**base, "status": "SKIPPED", "previous_state": "ALREADY_ACTIVE", "current_state": "ACTIVE",
                   "message": f"Conta de {account['name']} ja estava ativa. Nenhuma alteracao necessaria."}
        else:
            account.update(account_locked=False, failed_attempts=0, unlocked_at=base["timestamp"])
            res = {**base, "status": "SUCCESS", "previous_state": "LOCKED", "current_state": "ACTIVE",
                   "message": f"Conta de {account['name']} desbloqueada com sucesso no Active Directory."}

    return post_tool_use_hook("unlock_user_account", {"user_email": email, "reason": reason},
                              json.dumps(res, ensure_ascii=False))


def configure_vpn_failover_route(user_email: str, gateway: str = "BR-SA-02", ticket_id: str = "") -> str:
    """
    Provisiona rota de contingência da VPN corporativa para um usuário.

    Args:
        user_email: E-mail corporativo do usuário afetado.
        gateway: Gateway de contingência aprovado (apenas BR-SA-02).
        ticket_id: Chamado de origem (vai para a trilha de auditoria).
    """
    email = _norm_email(user_email)
    gw = (gateway or "").strip().upper()
    base = {"operation": "CONFIGURE_VPN_FAILOVER_ROUTE", "email": email, "target_gateway": gw, "timestamp": _now(),
            "audit_code": f"AUDIT-VPN-{uuid.uuid4().hex[:8].upper()}"}
    if not email.endswith(CORPORATE_DOMAIN):
        res = {**base, "status": "BLOCKED", "session_token": None,
               "message": f"Recusado: '{email}' nao pertence ao dominio corporativo."}
    elif email not in MOCK_AD_ACCOUNTS:
        res = {**base, "status": "FAILED", "session_token": None,
               "message": f"Conta {email} nao existe no Active Directory; rota nao provisionada."}
    elif gw not in APPROVED_VPN_GATEWAYS:
        res = {**base, "status": "BLOCKED", "session_token": None,
               "message": f"Recusado: gateway '{gw}' fora da lista aprovada {sorted(APPROVED_VPN_GATEWAYS)}."}
    else:
        res = {**base, "status": "SUCCESS", "session_token": f"VPN-FAILOVER-{uuid.uuid4().hex[:10].upper()}",
               "dns_servers": ["10.0.0.10", "10.0.0.11"],
               "message": f"Rota de contingencia atribuida para o gateway secundario {gw}."}
    return post_tool_use_hook("configure_vpn_failover_route", {"user_email": email, "gateway": gw, "ticket_id": ticket_id},
                              json.dumps(res, ensure_ascii=False))


def find_open_incident(ticket_id: str):
    """Incidente já aberto para o mesmo ticket (idempotência contra reenvio do orquestrador)."""
    return next((t for t in MOCK_ITSM_TICKETS.values() if t["original_ticket_id"] == ticket_id), None)


def dispatch_sla_incident(ticket_id: str, severity: str, team: str, justification: str) -> str:
    """
    Registra incidente no ITSM e calcula a meta de SLA pela matriz oficial
    (Critica 30, Alta 120, Media 480, Baixa 1440 minutos).

    Args:
        ticket_id: Chamado original.
        severity: Critica, Alta, Media ou Baixa (com ou sem acento).
        team: Equipe N2/N3 responsável.
        justification: Justificativa técnica do escalonamento.
    """
    sev_key = _fold(severity)
    args = {"ticket_id": ticket_id, "severity": severity, "team": team, "justification": justification[:500]}
    if sev_key not in SLA_MATRIX_MINUTES:
        res = {"status": "FAILED", "incident_number": None, "sla_target_minutes": None, "original_ticket_id": ticket_id,
               "message": f"Severidade '{severity}' invalida; use Critica, Alta, Media ou Baixa.", "dispatched_at": _now()}
        return post_tool_use_hook("dispatch_sla_incident", args, json.dumps(res, ensure_ascii=False))

    existing = find_open_incident(ticket_id)
    if existing:  # reenvio do mesmo ticket: devolve o incidente existente, sem duplicar
        res = {**existing, "status": "DISPATCHED", "deduplicated": True}
        return post_tool_use_hook("dispatch_sla_incident", args, json.dumps(res, ensure_ascii=False))

    incident_number = f"INC-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
    record = {
        "incident_number": incident_number,
        "original_ticket_id": ticket_id,
        "assigned_team": team,
        "severity": sev_key.capitalize(),
        "sla_target_minutes": SLA_MATRIX_MINUTES[sev_key],
        "on_call_engineer": "Plantao_N2_Engenharia",
        "status": "DISPATCHED",
        "justification": justification[:500],
        "dispatched_at": _now(),
    }
    MOCK_ITSM_TICKETS[incident_number] = record
    return post_tool_use_hook("dispatch_sla_incident", args, json.dumps(record, ensure_ascii=False))


if HAS_AGENTS_SDK:
    REMEDIATION_TOOLS = [function_tool(unlock_user_account), function_tool(configure_vpn_failover_route),
                         function_tool(dispatch_sla_incident)]
else:
    REMEDIATION_TOOLS = [unlock_user_account, configure_vpn_failover_route, dispatch_sla_incident]
