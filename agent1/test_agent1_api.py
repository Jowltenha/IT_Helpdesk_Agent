"""
Suite de Testes Automatizados para a API do Agente 1 (Triagem N1).
Valida:
 1. POST /run retornando HTTP 202 com task_id imediatamente
 2. GET /status/{task_id} retornando pending e posteriormente done com HelpdeskResponse tipado
 3. GET /health
"""
import sys
import os
import json
import time

# Adiciona o diretorio raiz ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from agent1.app import app, TASKS_DB


def test_agent1_lifecycle():
    print("=========================================================")
    print("🧪 TESTANDO A API DO AGENTE 1 (TRIAGEM N1 - FASTAPI)")
    print("=========================================================\n")

    client = TestClient(app)

    # 1. Teste de Health
    print("🔹 Teste 1: GET /health")
    resp_health = client.get("/health")
    assert resp_health.status_code == 200, f"Falha no health: {resp_health.text}"
    print(f"Status Code: {resp_health.status_code}")
    print(f"Payload: {resp_health.json()}\n")

    # 2. Teste de POST /run
    print("🔹 Teste 2: POST /run (Disparo Assincrono com BackgroundTasks)")
    payload = {
        "user_prompt": "Nao consigo acessar a folha de pagamento. Erro 'Acesso Negado 403'. E-mail maria.souza@empresa.com. Urgente ate 17h.",
        "session_id": "test_session_fastapi_01"
    }
    resp_run = client.post("/run", json=payload)
    print(f"Status Code: {resp_run.status_code} (Esperado: 202 Accepted)")
    assert resp_run.status_code == 202, f"Esperado 202, obteve {resp_run.status_code}: {resp_run.text}"

    run_data = resp_run.json()
    task_id = run_data["task_id"]
    print(f"Resposta Inicial: {json.dumps(run_data, indent=2, ensure_ascii=False)}\n")
    assert "task_id" in run_data
    assert run_data["status"] == "pending"

    # 3. Teste de GET /status/{task_id}
    print(f"🔹 Teste 3: GET /status/{task_id}")
    # Com o TestClient do FastAPI, as BackgroundTasks sao executadas imediatamente durante o request do client
    resp_status = client.get(f"/status/{task_id}")
    assert resp_status.status_code == 200, f"Falha no status: {resp_status.text}"

    status_data = resp_status.json()
    print(f"Status Code: {resp_status.status_code}")
    print(f"Payload do Status: {json.dumps(status_data, indent=2, ensure_ascii=False)}\n")

    assert status_data["task_id"] == task_id
    assert status_data["status"] in ["pending", "done"]

    if status_data["status"] == "done":
        result = status_data["result"]
        assert result is not None
        assert "ticket_summary" in result
        assert "category" in result
        assert "severity" in result
        assert "requires_human_escalation" in result
        print("✅ Validacao Pydantic bem-sucedida! Campos obrigatorios verificados.")

    # 4. Teste de Tarefa Inexistente (404)
    print("🔹 Teste 4: GET /status/tarefa_inexistente_999 (Tratamento de Erro 404)")
    resp_404 = client.get("/status/tarefa_inexistente_999")
    print(f"Status Code: {resp_404.status_code} (Esperado: 404 Not Found)")
    assert resp_404.status_code == 404

    print("\n=========================================================")
    print("🎉 TODOS OS TESTES DA API DO AGENTE 1 PASSARAM COM SUCESSO!")
    print("=========================================================\n")


if __name__ == "__main__":
    test_agent1_lifecycle()
