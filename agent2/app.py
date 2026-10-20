"""
Servico FastAPI do Agente 2 (Resolucao Automatizada N2 e Remediacao de TI).
Exponibiliza endpoints REST assincronos com BackgroundTasks:
 - POST /run: Retorna 202 Accepted com task_id imediatamente.
 - GET /status/{task_id}: Consulta o estado da tarefa (pending, done, error).
 - GET /health: Liveness probe do servico.
Porta padrao de execucao: 8002.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from agent2.models import (
    RemediationRequest,
    TaskInitiatedResponse,
    TaskStatusResponse,
    RemediationResponse
)
from agent2.runner import RemediationAgentRunner

app = FastAPI(
    title="Agent 2 - ITSM Remediation & Auto-Resolution API",
    description="Servico REST assincrono do Agente de Auto-Remediacao e Despacho N2 para o TP3.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Banco em memoria de tarefas assincronas do Agente 2
TASKS_DB: Dict[str, Dict[str, Any]] = {}
runner = RemediationAgentRunner()


async def process_remediation_task(task_id: str, request_data: RemediationRequest):
    """
    Funcao executada em segundo plano via BackgroundTasks do FastAPI.
    """
    try:
        result: RemediationResponse = await runner.run(request=request_data)
        TASKS_DB[task_id]["status"] = "done"
        TASKS_DB[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        TASKS_DB[task_id]["result"] = result
    except Exception as exc:
        TASKS_DB[task_id]["status"] = "error"
        TASKS_DB[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        TASKS_DB[task_id]["error"] = str(exc)


@app.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskInitiatedResponse,
    summary="Inicia a execucao assincrona de uma operacao de remediacao",
    description="Recebe a solicitacao de resolucao/despacho, despacha em BackgroundTasks e retorna 202 imediatamente."
)
async def run_remediation(payload: RemediationRequest, background_tasks: BackgroundTasks):
    task_id = f"rem_task_{uuid.uuid4().hex[:12]}"
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
        "version": "1.0.0",
        "active_tasks_count": len(TASKS_DB)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent2.app:app", host="0.0.0.0", port=8002, reload=True)
