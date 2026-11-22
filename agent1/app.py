"""
Serviço FastAPI do Agente 1 (Triagem de TI Nível 1) — porta 8001.
 - POST /run: 202 Accepted com task_id imediatamente (processamento em BackgroundTasks).
 - GET /status/{task_id}: pending | done | error.
 - GET /health: liveness + versão do prompt.

TP5: timeout por tarefa (AGENT1_TASK_TIMEOUT_SECONDS) — uma tarefa nunca fica 'pending'
para sempre; ao estourar vira 'error' com mensagem clara, que o n8n trata como falha.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from agent1.models import HelpdeskResponse, RunRequest, TaskInitiatedResponse, TaskStatusResponse
from agent1.runner import PROMPT_VERSION, HelpdeskAgentRunner

TASK_TIMEOUT_SECONDS = float(os.getenv("AGENT1_TASK_TIMEOUT_SECONDS", "100"))

from agent1.security import API_TOKEN, make_api_key_dependency  # noqa: E402

require_api_key = make_api_key_dependency(lambda: API_TOKEN)

app = FastAPI(
    title="Agent 1 - IT Helpdesk N1 Triage API",
    description="Serviço REST assíncrono do Agente de Triagem de TI N1.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8000,http://localhost:5678").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

TASKS_DB: Dict[str, Dict[str, Any]] = {}
runner = HelpdeskAgentRunner()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def process_agent_task(task_id: str, user_prompt: str, session_id: str):
    """Executada em segundo plano via BackgroundTasks."""
    try:
        result: HelpdeskResponse = await asyncio.wait_for(
            runner.run(user_prompt=user_prompt, session_id=session_id), timeout=TASK_TIMEOUT_SECONDS
        )
        TASKS_DB[task_id].update(status="done", completed_at=_now(), result=result)
    except asyncio.TimeoutError:
        TASKS_DB[task_id].update(
            status="error", completed_at=_now(),
            error=f"AGENT1_TIMEOUT: triagem excedeu {int(TASK_TIMEOUT_SECONDS)}s.",
        )
    except Exception as exc:  # noqa: BLE001
        TASKS_DB[task_id].update(status="error", completed_at=_now(), error=f"{type(exc).__name__}: {exc}")


@app.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
    response_model=TaskInitiatedResponse,
    summary="Inicia a triagem assíncrona de um chamado de TI",
)
async def run_ticket_triage(payload: RunRequest, background_tasks: BackgroundTasks):
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    TASKS_DB[task_id] = {
        "task_id": task_id, "status": "pending", "created_at": _now(),
        "completed_at": None, "result": None, "error": None,
    }
    background_tasks.add_task(
        process_agent_task, task_id=task_id, user_prompt=payload.user_prompt,
        session_id=payload.session_id or "default_session",
    )
    return TaskInitiatedResponse(
        task_id=task_id, status="pending",
        message="Chamado recebido com sucesso. Processamento de triagem iniciado em background.",
    )


@app.get("/status/{task_id}", response_model=TaskStatusResponse, dependencies=[Depends(require_api_key)], summary="Consulta o status e o resultado de uma tarefa")
async def get_task_status(task_id: str):
    if task_id not in TASKS_DB:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tarefa '{task_id}' nao encontrada.")
    return TaskStatusResponse(**TASKS_DB[task_id])


@app.get("/health", summary="Verificação de integridade do serviço")
async def health_check():
    return {
        "status": "ok",
        "agent": "Agent 1 - Helpdesk N1 Triage",
        "version": app.version,
        "prompt_version": PROMPT_VERSION,
        "auth_enabled": API_TOKEN is not None,
        "model": runner.model_name,
        "embedding_model": runner.rag.embedding_model,
        "active_tasks_count": sum(1 for t in TASKS_DB.values() if t["status"] == "pending"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent1.app:app", host="0.0.0.0", port=8001)
