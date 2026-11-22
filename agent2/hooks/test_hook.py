"""
Script de teste automatizado para o Hook PostToolUse do Agente 2.
Comprova a injeção do hash de compliance SHA-256 e o registro em security_audit.log.
"""
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from agent2.hooks.post_tool_auditor import post_tool_use_hook, AUDIT_LOG_PATH


def run_tests():
    print("=== EXECUTANDO TESTES DO HOOK POSTTOOLUSE (AGENTE 2) ===")

    # TP5: security_audit.log é append-only (settings.json nega removê-lo); não apagamos mais.
    lines_before = 0
    if os.path.exists(AUDIT_LOG_PATH):
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            lines_before = sum(1 for _ in f)

    test_actions = [
        {
            "tool": "unlock_user_account",
            "args": {"user_email": "maria.souza@empresa.com", "reason": "Chamado TCK-101"},
            "raw_output": json.dumps({"status": "SUCCESS", "audit_code": "AUDIT-AD-01", "email": "maria.souza@empresa.com"})
        },
        {
            "tool": "configure_vpn_failover_route",
            "args": {"user_email": "carlos.lima@empresa.com", "gateway": "BR-SA-02"},
            "raw_output": json.dumps({"status": "SUCCESS", "session_token": "VPN-FAILOVER-99", "target_gateway": "BR-SA-02"})
        },
        {
            "tool": "dispatch_sla_incident",
            "args": {"ticket_id": "TCK-999", "severity": "Critica", "team": "N2 Infraestrutura"},
            "raw_output": json.dumps({"status": "SUCCESS", "incident_number": "INC-202611-001", "sla_target_minutes": 30})
        }
    ]

    for idx, act in enumerate(test_actions, 1):
        processed_str = post_tool_use_hook(act["tool"], act["args"], act["raw_output"])
        data = json.loads(processed_str)

        assert "compliance_hash" in data, f"Falha no teste {idx}: compliance_hash ausente!"
        assert data["compliance_hash"].startswith("SEC-"), f"Falha no teste {idx}: prefixo SEC- ausente!"
        assert data.get("verified_by_hook") is True, f"Falha no teste {idx}: verified_by_hook deve ser True!"

        print(f"[{idx}] Tool '{act['tool']}': ✅ PASSOU")
        print(f"     Compliance Hash: {data['compliance_hash']} | Status: {data['status']}")

    assert os.path.exists(AUDIT_LOG_PATH), "Arquivo security_audit.log não foi gerado!"
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = len(lines) - lines_before
    assert new_lines == len(test_actions), f"Esperado {len(test_actions)} novos registros, encontrado {new_lines}"
    print(f"\nNovos eventos criptografados registrados: {new_lines}")
    print("🎉 TODOS OS TESTES DO HOOK POSTTOOLUSE FORAM APROVADOS!")


if __name__ == "__main__":
    run_tests()
