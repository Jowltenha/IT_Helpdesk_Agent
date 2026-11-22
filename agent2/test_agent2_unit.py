"""
Testes unitários do Agente 2 (sem LLM). Rodar: python -m pytest agent2/test_agent2_unit.py -q
Cobrem os refinamentos do TP5: contrato estrito, política determinística e ferramentas seguras.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent2.models import RemediationRequest
from agent2.runner import plan_actions
from agent2.tools import (configure_vpn_failover_route, dispatch_sla_incident, reset_mock_state,
                          unlock_user_account)

BASE = dict(ticket_id="TCK-UNIT-1", user_email="maria.souza@empresa.com", category="Acessos/Senhas",
            severity="Alta", recommended_action="Desbloquear conta", requires_human_escalation=False)


@pytest.fixture(autouse=True)
def _reset():
    reset_mock_state()


def test_external_email_rejected_by_contract():
    with pytest.raises(ValueError):
        RemediationRequest(**{**BASE, "user_email": "atacante@gmail.com"})


def test_trailing_dot_and_accents_normalized():
    r = RemediationRequest(**{**BASE, "user_email": "maria.souza@empresa.com.", "severity": "Média",
                              "action_type": "NONE"})
    assert (r.user_email, r.severity, r.action_type) == ("maria.souza@empresa.com", "Media", None)


def test_invalid_category_rejected():
    with pytest.raises(ValueError):
        RemediationRequest(**{**BASE, "category": "Impressoras"})


def test_policy_human_escalation_only_dispatches():
    req = RemediationRequest(**{**BASE, "requires_human_escalation": True, "action_type": "UNLOCK_ACCOUNT",
                                "recommended_action": "desbloqueio exige confirmacao de identidade por telefone"})
    assert plan_actions(req)[0] == ["DISPATCH_INCIDENT"]


def test_policy_ignores_free_text_keywords():
    req = RemediationRequest(**{**BASE, "category": "Software", "action_type": "DISPATCH_INCIDENT",
                                "recommended_action": "conta bloqueada, unlock, vpn, gateway, redefinicao"})
    assert plan_actions(req)[0] == ["DISPATCH_INCIDENT"]


@pytest.mark.parametrize("category,expected", [("Acessos/Senhas", "UNLOCK_ACCOUNT"), ("Redes/VPN", "VPN_FAILOVER"),
                                               ("Hardware", "DISPATCH_INCIDENT")])
def test_policy_auto_detect_by_category(category, expected):
    req = RemediationRequest(**{**BASE, "category": category, "action_type": "AUTO_DETECT"})
    assert plan_actions(req)[0] == [expected]


def test_unlock_locked_account_then_idempotent():
    first = json.loads(unlock_user_account("maria.souza@empresa.com"))
    second = json.loads(unlock_user_account("maria.souza@empresa.com"))
    assert first["status"] == "SUCCESS" and first["previous_state"] == "LOCKED"
    assert second["status"] == "SKIPPED"
    assert first["compliance_hash"].startswith("SEC-")


def test_unlock_unknown_account_fails_without_change():
    out = json.loads(unlock_user_account("nao.existe@empresa.com"))
    assert out["status"] == "FAILED" and out["previous_state"] == "NOT_FOUND"


def test_unlock_external_domain_blocked():
    assert json.loads(unlock_user_account("atacante@gmail.com"))["status"] == "BLOCKED"


def test_vpn_unapproved_gateway_blocked():
    assert json.loads(configure_vpn_failover_route("joao.silva@empresa.com", "EVIL-GW"))["status"] == "BLOCKED"


@pytest.mark.parametrize("sev,minutes", [("Crítica", 30), ("Alta", 120), ("Média", 480), ("baixa", 1440)])
def test_sla_matrix_with_accents(sev, minutes):
    assert json.loads(dispatch_sla_incident("TCK-1", sev, "N2", "x"))["sla_target_minutes"] == minutes


def test_sla_invalid_severity_fails():
    assert json.loads(dispatch_sla_incident("TCK-1", "Urgentissima", "N2", "x"))["status"] == "FAILED"


def test_missing_email_falls_back_to_dispatch():
    req = RemediationRequest(**{**BASE, "user_email": None, "action_type": "UNLOCK_ACCOUNT"})
    assert plan_actions(req)[0] == ["DISPATCH_INCIDENT"]


def test_api_token_required_when_configured(monkeypatch):
    from fastapi.testclient import TestClient
    from agent2 import app as app_module
    monkeypatch.setattr(app_module, "API_TOKEN", "segredo-teste")
    client = TestClient(app_module.app)
    payload = {**BASE, "ticket_id": "TCK-AUTH"}
    assert client.post("/run", json=payload).status_code == 401
    assert client.post("/run", json=payload, headers={"X-API-Key": "errado"}).status_code == 401
    assert client.post("/run", json=payload, headers={"X-API-Key": "segredo-teste"}).status_code == 202
    assert client.get("/health").status_code == 200


# ---------------- TP5 rodada 2 (revisão do Claude Code em agent2/) ----------------
@pytest.mark.parametrize("action,category", [("UNLOCK_ACCOUNT", "Hardware"), ("UNLOCK_ACCOUNT", "Software"),
                                             ("VPN_FAILOVER", "Acessos/Senhas")])
def test_policy_rejects_action_category_conflict(action, category):
    req = RemediationRequest(**{**BASE, "category": category, "action_type": action})
    planned, reason = plan_actions(req)
    assert planned == ["DISPATCH_INCIDENT"] and "Conflito" in reason


def test_vpn_unknown_account_fails():
    out = json.loads(configure_vpn_failover_route("nao.existe@empresa.com", "BR-SA-02", ticket_id="TCK-X"))
    assert out["status"] == "FAILED" and out["audit_code"].startswith("AUDIT-VPN-")


def test_dispatch_is_idempotent_per_ticket():
    a = json.loads(dispatch_sla_incident("TCK-IDEMP", "Alta", "N2", "x"))
    b = json.loads(dispatch_sla_incident("TCK-IDEMP", "Alta", "N2", "x"))
    assert a["incident_number"] == b["incident_number"] and b.get("deduplicated") is True


def test_failed_unlock_opens_fallback_incident(monkeypatch):
    import asyncio
    from agent2.runner import RemediationAgentRunner

    async def no_llm(self, *args, **kwargs):
        return "resumo", "template"

    monkeypatch.setattr(RemediationAgentRunner, "_summarize", no_llm)
    runner = RemediationAgentRunner()
    runner.log_path = os.devnull
    req = RemediationRequest(**{**BASE, "ticket_id": "TCK-FALLBACK", "user_email": "nao.existe@empresa.com",
                                "action_type": "UNLOCK_ACCOUNT"})
    resp = asyncio.run(runner.run(req))
    assert [a.status for a in resp.actions_executed] == ["FAILED", "DISPATCHED"]
    assert resp.status == "ESCALATED" and resp.escalation_team == "N2 Acessos e Identidade"


def test_api_idempotent_by_ticket_id():
    from fastapi.testclient import TestClient
    from agent2 import app as app_module
    client = TestClient(app_module.app)
    hdr = {"X-API-Key": app_module.API_TOKEN} if app_module.API_TOKEN else {}
    payload = {**BASE, "ticket_id": "TCK-API-IDEMP", "requires_human_escalation": True}
    r1 = client.post("/run", json=payload, headers=hdr).json()
    r2 = client.post("/run", json=payload, headers=hdr).json()
    assert r1["task_id"] == r2["task_id"]
