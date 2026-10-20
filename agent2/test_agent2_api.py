"""
Suite de Testes Automatizados para a API do Agente 2 (Auto-Remediacao e Despacho N2).
Valida:
 1. GET /health na porta 8002
 2. POST /run retornando HTTP 202 com task_id imediatamente
 3. GET /status/{task_id} retornando status done com RemediationResponse e auditoria
 4. Execucao de desbloqueio de conta e despacho com calculo de SLA
"""
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from agent2.app import app


def test_agent2_lifecycle():
    print("=========================================================")
    print("🧪 TESTANDO A API DO AGENTE 2 (REMEDIACAO N2 - FASTAPI)")
    print("=========================================================\n")

    client = TestClient(app)

    # 1. Teste de Health
    print("🔹 Teste 1: GET /health (Agente 2)")
    resp_health = client.get("/health")
    assert resp_health.status_code == 200, f"Falha no health: {resp_health.text}"
    print(f"Status Code: {resp_health.status_code}")
    print(f"Payload: {resp_health.json()}\n")

    # 2. Teste de POST /run - Caso 1: Desbloqueio Automatico de Conta (Auto-remediation)
    print("🔹 Teste 2: POST /run - Desbloqueio de Conta (Active Directory)")
    payload_unlock = {
        "ticket_id": "TCK-40301-BR",
        "user_email": "maria.souza@empresa.com",
        "category": "Acessos/Senhas",
        "severity": "Alta",
        "recommended_action": "Solicitar desbloqueio da conta no Active Directory para liberacao do sistema de folha de pagamento.",
        "requires_human_escalation": False,
        "action_type": "UNLOCK_ACCOUNT"
    }
    resp_run = client.post("/run", json=payload_unlock)
    print(f"Status Code: {resp_run.status_code} (Esperado: 202 Accepted)")
    assert resp_run.status_code == 202, f"Esperado 202, obteve {resp_run.status_code}: {resp_run.text}"

    data_run = resp_run.json()
    task_id = data_run["task_id"]
    print(f"Resposta Inicial: {json.dumps(data_run, indent=2, ensure_ascii=False)}\n")
    assert "task_id" in data_run
    assert data_run["status"] == "pending"

    # 3. Teste de GET /status/{task_id} para Caso 1
    print(f"🔹 Teste 3: GET /status/{task_id} (Verificacao de Conclusao e Auditoria)")
    resp_status = client.get(f"/status/{task_id}")
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    print(f"Payload do Status: {json.dumps(status_data, indent=2, ensure_ascii=False)}\n")

    assert status_data["task_id"] == task_id
    assert status_data["status"] == "done"
    result = status_data["result"]
    assert result["status"] == "SUCCESS"
    assert len(result["actions_executed"]) >= 1
    assert any(a["action_name"] == "unlock_user_account" for a in result["actions_executed"])
    assert len(result["audit_trail"]) >= 1
    print("✅ Sucesso: Conta desbloqueada com codigo de auditoria emitido.")

    # 4. Teste de POST /run - Caso 2: Falha Grave com Escalonamento e SLA (ITSM Dispatch)
    print("🔹 Teste 4: POST /run - Incidente com Escalonamento Humano e Computacao de SLA")
    payload_escalation = {
        "ticket_id": "TCK-99002-HW",
        "user_email": "carlos.moraes@empresa.com",
        "category": "Hardware",
        "severity": "Critica",
        "recommended_action": "Troca de fonte de alimentacao e analise presencial obrigatoria.",
        "requires_human_escalation": True,
        "action_type": "DISPATCH_INCIDENT"
    }
    resp_run_esc = client.post("/run", json=payload_escalation)
    assert resp_run_esc.status_code == 202
    task_id_esc = resp_run_esc.json()["task_id"]

    resp_status_esc = client.get(f"/status/{task_id_esc}")
    assert resp_status_esc.status_code == 200
    status_esc_data = resp_status_esc.json()
    print(f"Payload de Escalonamento: {json.dumps(status_esc_data, indent=2, ensure_ascii=False)}\n")

    result_esc = status_esc_data["result"]
    assert result_esc["status"] == "ESCALATED"
    assert result_esc["sla_target_minutes"] == 30  # SLA de Severidade Critica
    assert result_esc["escalation_team"] is not None
    print(f"✅ Sucesso: Incidente escalado para {result_esc['escalation_team']} com SLA de {result_esc['sla_target_minutes']} min.")

    # 5. Teste de 404
    print("🔹 Teste 5: GET /status/tarefa_inexistente (Validacao de Erro 404)")
    resp_404 = client.get("/status/rem_task_999999")
    assert resp_404.status_code == 404
    print("✅ Status 404 validado corretamente.")

    print("\n=========================================================")
    print("🎉 TODOS OS TESTES DA API DO AGENTE 2 PASSARAM COM SUCESSO!")
    print("=========================================================\n")


if __name__ == "__main__":
    test_agent2_lifecycle()
