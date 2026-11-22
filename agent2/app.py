"""
Servico FastAPI do Agente 2 (Resolucao Automatizada N2 e Remediacao de TI).
Exponibiliza endpoints REST assincronos com BackgroundTasks:
 - POST /run: Retorna 202 Accepted com task_id imediatamente.
 - GET /status/{task_id}: Consulta o estado da tarefa (pending, done, error).
 - GET /health: Liveness probe do servico.
Porta padrao de execucao: 8002.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from agent2.models import (
    RemediationRequest,
    TaskInitiatedResponse,
    TaskStatusResponse,
    RemediationResponse
)
from agent2.runner import PROMPT_VERSION, RemediationAgentRunner

TASK_TIMEOUT_SECONDS = float(os.getenv("AGENT2_TASK_TIMEOUT_SECONDS", "100"))

from agent2.security import API_TOKEN, make_api_key_dependency  # noqa: E402

require_api_key = make_api_key_dependency(lambda: API_TOKEN)

app = FastAPI(
    title="Agent 2 - ITSM Remediation & Auto-Resolution API",
    description="Servico REST assincrono do Agente de Auto-Remediacao e Despacho N2 (TP5: timeout por tarefa e contrato de entrada estrito).",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8000,http://localhost:5678").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Banco em memoria de tarefas assincronas do Agente 2
TASKS_DB: Dict[str, Dict[str, Any]] = {}
TICKET_INDEX: Dict[str, str] = {}  # ticket_id -> task_id (idempotência)
runner = RemediationAgentRunner()


async def process_remediation_task(task_id: str, request_data: RemediationRequest):
    """
    Funcao executada em segundo plano via BackgroundTasks do FastAPI.
    """
    try:
        result: RemediationResponse = await asyncio.wait_for(runner.run(request=request_data), timeout=TASK_TIMEOUT_SECONDS)
        TASKS_DB[task_id]["status"] = "done"
        TASKS_DB[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        TASKS_DB[task_id]["result"] = result
    except asyncio.TimeoutError:
        TASKS_DB[task_id]["status"] = "error"
        TASKS_DB[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        TASKS_DB[task_id]["error"] = f"AGENT2_TIMEOUT: remediacao excedeu {int(TASK_TIMEOUT_SECONDS)}s."
    except Exception as exc:
        TASKS_DB[task_id]["status"] = "error"
        TASKS_DB[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        TASKS_DB[task_id]["error"] = f"{type(exc).__name__}: {exc}"


@app.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
    response_model=TaskInitiatedResponse,
    summary="Inicia a execucao assincrona de uma operacao de remediacao",
    description="Recebe a solicitacao de resolucao/despacho, despacha em BackgroundTasks e retorna 202 imediatamente."
)
async def run_remediation(payload: RemediationRequest, background_tasks: BackgroundTasks):
    # Idempotência (TP5, rodada 2): o n8n reenvia o POST em caso de falha transitória
    # (retryOnFail). O mesmo ticket_id devolve a tarefa já existente em vez de repetir ações.
    existing = TICKET_INDEX.get(payload.ticket_id)
    if existing and TASKS_DB.get(existing, {}).get("status") in ("pending", "done"):
        return TaskInitiatedResponse(task_id=existing, status=TASKS_DB[existing]["status"],
                                     message="Ticket ja recebido anteriormente; devolvendo a tarefa existente (idempotente).")
    task_id = f"rem_task_{uuid.uuid4().hex[:12]}"
    TICKET_INDEX[payload.ticket_id] = task_id
    now_iso = datetime.now(timezone.utc).isoformat()

    TASKS_DB[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "created_at": now_iso,
        "completed_at": None,
        "result": None,
        "error": None
    }

    background_tasks.add_task(
        process_remediation_task,
        task_id=task_id,
        request_data=payload
    )

    return TaskInitiatedResponse(
        task_id=task_id,
        status="pending",
        message="Operacao de remediacao registrada com sucesso. Execucao iniciada em background."
    )


@app.get(
    "/status/{task_id}",
    dependencies=[Depends(require_api_key)],
    response_model=TaskStatusResponse,
    summary="Consulta o status e o resultado da tarefa de remediacao",
    description="Retorna pending, done ou error. Quando concluido, inclui o RemediationResponse tipado."
)
async def get_task_status(task_id: str):
    if task_id not in TASKS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarefa '{task_id}' nao encontrada no Agente 2."
        )

    task_data = TASKS_DB[task_id]
    return TaskStatusResponse(
        task_id=task_data["task_id"],
        status=task_data["status"],
        created_at=task_data["created_at"],
        completed_at=task_data["completed_at"],
        result=task_data["result"],
        error=task_data["error"]
    )


@app.get("/health", summary="Verificacao de integridade do servico")
async def health_check():
    return {
        "status": "ok",
        "agent": "Agent 2 - Remediation & ITSM Dispatcher",
        "version": app.version,
        "prompt_version": PROMPT_VERSION,
        "auth_enabled": API_TOKEN is not None,
        "active_tasks_count": sum(1 for t in TASKS_DB.values() if t["status"] == "pending")
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent2.app:app", host="0.0.0.0", port=8002)
