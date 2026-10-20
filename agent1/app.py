"""
Servico FastAPI do Agente 1 (Triagem de TI Nivel 1).
Exponibiliza endpoints REST assincronos com BackgroundTasks:
 - POST /run: Retorna 202 Accepted com task_id imediatamente.
 - GET /status/{task_id}: Consulta o estado da tarefa (pending, done, error).
 - GET /health: Liveness probe do servico.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from agent1.models import (
    RunRequest,
    TaskInitiatedResponse,
    TaskStatusResponse,
    HelpdeskResponse
)
from agent1.runner import HelpdeskAgentRunner

app = FastAPI(
    title="Agent 1 - IT Helpdesk N1 Triage API",
    description="Servico REST assincrono do Agente de Triagem de TI N1 para o TP3.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Banco em memoria para rastreamento de tarefas assincronas
TASKS_DB: Dict[str, Dict[str, Any]] = {}
runner = HelpdeskAgentRunner()


async def process_agent_task(task_id: str, user_prompt: str, session_id: str):
    """
    Funcao executada em segundo plano via FastAPI BackgroundTasks.
    """
    try:
        result: HelpdeskResponse = await runner.run(user_prompt=user_prompt, session_id=session_id)
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
    summary="Inicia a triagem assincrona de um chamado de TI",
    description="Recebe o chamado, despacha a execucao em BackgroundTasks e retorna 202 com task_id imediatamente."
)
async def run_ticket_triage(payload: RunRequest, background_tasks: BackgroundTasks):
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Registra o estado inicial pendente
    TASKS_DB[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "created_at": now_iso,
        "completed_at": None,
        "result": None,
        "error": None
    }

    # Despacha para execucao assincrona sem bloquear o HTTP
    background_tasks.add_task(
        process_agent_task,
        task_id=task_id,
        user_prompt=payload.user_prompt,
        session_id=payload.session_id or "default_session"
    )

    return TaskInitiatedResponse(
        task_id=task_id,
        status="pending",
        message="Chamado recebido com sucesso. Processamento de triagem iniciado em background."
    )


@app.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Consulta o status e o resultado de uma tarefa",
    description="Retorna o status atual (pending, done, error). Quando concluido, inclui o payload estruturado de HelpdeskResponse."
)
async def get_task_status(task_id: str):
    if task_id not in TASKS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarefa '{task_id}' nao encontrada."
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
        "agent": "Agent 1 - Helpdesk N1 Triage",
        "version": "1.0.0",
        "active_tasks_count": len(TASKS_DB)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent1.app:app", host="0.0.0.0", port=8001, reload=True)
