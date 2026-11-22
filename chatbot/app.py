"""
Chatbot Corporativo de Autoatendimento de TI em Chainlit.
Atende ao Requisito 9 do Projeto (Slide 8):
"Gatilho (trigger) que dispara o workflow n8n — Escolha única: Chatbot Corporativo Web via Webhook"

Interface conversacional para colaboradores reportarem incidentes em linguagem natural,
mantendo o session_id persistente para a SQLiteSession e acionando o Webhook do n8n.
"""
import os
import sys
import json
import uuid
import asyncio
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    # Permite importar os hooks de agent1/ e agent2/. Usa append (e não insert(0, ...))
    # porque o Chainlit faz sys.path.pop(0) logo depois de carregar este arquivo, o que
    # removeria o caminho do projeto e quebraria o import ("No module named 'agent1'").
    sys.path.append(PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

try:
    import chainlit as cl
    HAS_CHAINLIT = True
except ImportError:
    HAS_CHAINLIT = False

# Configurações de endpoints
# TP4 (assíncrono): o webhook responde 202 + ticket_id na hora; o chatbot consulta o
# andamento em N8N_STATUS_URL enquanto o n8n processa os agentes em segundo plano.
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/helpdesk-triage-tp4")
N8N_STATUS_URL = os.getenv("N8N_STATUS_URL", "http://localhost:5678/webhook/helpdesk-status")
AGENT1_API_URL = os.getenv("AGENT1_API_URL", "http://localhost:8001")
AGENT2_API_URL = os.getenv("AGENT2_API_URL", "http://localhost:8002")
LLM_PROXY_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
# TP5: o Agente 1 exige X-API-Key quando AGENT1_API_TOKEN está definido (.env)
AGENT1_HEADERS = {"X-API-Key": os.getenv("AGENT1_API_TOKEN")} if os.getenv("AGENT1_API_TOKEN") else {}
POLL_INTERVAL_SECONDS = 3.0
POLL_MAX_ATTEMPTS = 60  # ~3 minutos

PRE_TOOL_LOG = os.path.join(PROJECT_ROOT, "agent1", "hooks", "hook_audit.log")
POST_TOOL_LOG = os.path.join(PROJECT_ROOT, "agent2", "hooks", "security_audit.log")


# ---------------------------------------------------------------------------
# Painel de diagnóstico (substitui os comandos curl/terminal do roteiro)
# ---------------------------------------------------------------------------
async def check_services() -> str:
    """Verifica se todos os componentes do pipeline estão no ar."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    checks = [
        ("Agente 1 — Triagem N1", f"{AGENT1_API_URL}/health", {}, (200,)),
        ("Agente 2 — Remediação N2", f"{AGENT2_API_URL}/health", {}, (200,)),
        # 404 + "not_found" significa que o webhook de produção está ativo (workflow publicado)
        ("n8n — Workflow TP4 publicado", f"{N8N_STATUS_URL}?ticket_id=verificacao", {}, (200, 404)),
        ("9Router — Proxy do LLM (chave do .env)", f"{LLM_PROXY_URL}/models",
         {"Authorization": f"Bearer {api_key}"}, (200,)),
    ]
    rows = []
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url, headers, ok_codes in checks:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code in ok_codes:
                    rows.append(f"| ✅ | {name} | `HTTP {resp.status_code}` |")
                elif resp.status_code == 401:
                    rows.append(f"| ❌ | {name} | `HTTP 401` — chave inválida no `.env` |")
                else:
                    rows.append(f"| ❌ | {name} | `HTTP {resp.status_code}` — workflow não publicado? |")
            except Exception as ex:
                rows.append(f"| ❌ | {name} | desligado (`{type(ex).__name__}`) |")
    all_ok = all(r.startswith("| ✅") for r in rows)
    header = "### 🩺 Verificação dos Serviços\n\n| | Componente | Resultado |\n| :-: | :--- | :--- |\n"
    footer = "\n\n**Tudo pronto para abrir um chamado.**" if all_ok else "\n\n⚠️ Corrija os itens com ❌ antes de continuar."
    return header + "\n".join(rows) + footer


async def fetch_ticket_status(ticket_id: str) -> str:
    """Consulta o webhook de status do n8n (o mesmo endpoint que o chatbot usa no polling)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(N8N_STATUS_URL, params={"ticket_id": ticket_id})
    body = json.dumps(resp.json(), indent=2, ensure_ascii=False)
    return (
        f"### 🔎 Status no n8n — `GET /webhook/helpdesk-status?ticket_id={ticket_id}`\n\n"
        f"**HTTP {resp.status_code}**\n\n```json\n{body}\n```"
    )


def run_hook_tests() -> str:
    """Executa os hooks PreToolUse (Agente 1) e PostToolUse (Agente 2) com casos de teste."""
    from agent1.hooks.pre_tool_validator import pre_tool_use_hook
    from agent2.hooks.post_tool_auditor import post_tool_use_hook

    pre_cases = [
        ("E-mail corporativo válido", "lookup_user_account", {"user_email": "maria.souza@empresa.com"}, True),
        ("E-mail externo (gmail)", "lookup_user_account", {"user_email": "invasor@gmail.com"}, False),
        ("Injeção de comando no e-mail", "lookup_user_account", {"user_email": "maria@empresa.com; rm -rf /"}, False),
        ("Serviço monitorado (vpn)", "check_system_status", {"service_name": "vpn"}, True),
        ("Injeção no nome do serviço", "check_system_status", {"service_name": "vpn; cat /etc/passwd"}, False),
        ("Ferramenta fora da política", "delete_user", {"user_email": "maria.souza@empresa.com"}, False),
    ]
    pre_rows, passed = [], 0
    for name, tool, args, expected in pre_cases:
        allowed, reason, _ = pre_tool_use_hook(tool, args)
        ok = allowed == expected
        passed += ok
        verdict = "🟢 permitido" if allowed else "🔴 bloqueado"
        pre_rows.append(f"| {'✅' if ok else '❌'} | {name} | `{tool}` | {verdict} | {reason} |")

    raw = json.dumps({"status": "SUCCESS", "audit_code": "AUDIT-AD-DEMO", "email": "maria.souza@empresa.com"})
    post = json.loads(post_tool_use_hook(
        "unlock_user_account",
        {"user_email": "maria.souza@empresa.com", "reason": "Demonstração do hook pelo chatbot"},
        raw,
    ))
    post_ok = post.get("verified_by_hook") is True and str(post.get("compliance_hash", "")).startswith("SEC-")

    return (
        "### 🛡️ Teste dos Hooks de Segurança\n\n"
        "**Hook `PreToolUse` — Agente 1** (roda *antes* de cada ferramenta):\n\n"
        "| | Caso | Ferramenta | Decisão do hook | Motivo |\n| :-: | :--- | :--- | :--- | :--- |\n"
        + "\n".join(pre_rows)
        + f"\n\n**{passed}/{len(pre_cases)} casos corretos.** Cada decisão foi gravada em `agent1/hooks/hook_audit.log`.\n\n"
        "---\n\n"
        "**Hook `PostToolUse` — Agente 2** (roda *depois* de cada ação de remediação):\n\n"
        "| Campo injetado pelo hook | Valor |\n| :--- | :--- |\n"
        f"| `compliance_hash` (SHA-256) | `{post.get('compliance_hash')}` |\n"
        f"| `verified_by_hook` | `{post.get('verified_by_hook')}` |\n"
        f"| `hook_processed_at` | `{post.get('hook_processed_at')}` |\n\n"
        f"{'✅' if post_ok else '❌'} Evento gravado em `agent2/hooks/security_audit.log`."
    )


def _read_jsonl(path: str) -> list:
    entries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return entries


def _parse_ts(value: str):
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def ticket_audit_trail(ticket_id: str, created_at: str, completed_at: str = "") -> str:
    """Mostra o que os hooks registraram durante o processamento real deste chamado."""
    # O log do PreToolUse não guarda o ticket_id, então os eventos são associados ao
    # chamado pela janela de tempo [created_at, completed_at] do processamento.
    start = _parse_ts(created_at or "")
    end = _parse_ts(completed_at or "")

    def in_window(entry: dict) -> bool:
        ts = _parse_ts(entry.get("timestamp", ""))
        if not start or not ts:
            return False
        return ts >= start and (end is None or ts <= end)

    pre = [e for e in _read_jsonl(PRE_TOOL_LOG) if in_window(e)]
    post = [e for e in _read_jsonl(POST_TOOL_LOG)
            if ticket_id in json.dumps(e.get("arguments", {}), ensure_ascii=False)]

    pre_rows = "\n".join(
        f"| `{e.get('tool_name')}` | {'🟢 permitido' if e.get('allowed') else '🔴 bloqueado'} | "
        f"`{json.dumps(e.get('arguments', {}), ensure_ascii=False)[:80]}` |"
        for e in pre[-10:]
    ) or "| — | nenhum evento | — |"
    post_rows = "\n".join(
        f"| `{e.get('tool_name')}` | `{e.get('status')}` | `{e.get('compliance_hash')}` | `{e.get('audit_code')}` |"
        for e in post
    ) or "| — | o Agente 2 não executou ações | — | — |"

    return (
        f"### 📜 Trilha de Auditoria dos Hooks — ticket `{ticket_id}`\n\n"
        "**PreToolUse (Agente 1)** — validações feitas antes de cada ferramenta da triagem:\n\n"
        "| Ferramenta | Decisão | Argumentos validados |\n| :--- | :--- | :--- |\n"
        f"{pre_rows}\n\n"
        "**PostToolUse (Agente 2)** — hash de compliance gerado após cada ação de remediação:\n\n"
        "| Ação | Status | Hash SHA-256 | Código de auditoria |\n| :--- | :--- | :--- | :--- |\n"
        f"{post_rows}"
    )


def ticket_actions(ticket_id: str, created_at: str, completed_at: str = ""):
    payload = {"ticket_id": ticket_id, "created_at": created_at, "completed_at": completed_at}
    return [
        cl.Action(name="ticket_status", label="Consultar status no n8n", icon="search", payload=payload),
        cl.Action(name="ticket_audit", label="Ver trilha de auditoria dos hooks", icon="shield-check", payload=payload),
    ]


def panel_actions():
    return [
        cl.Action(name="check_services", label="Verificar serviços", icon="activity", payload={}),
        cl.Action(name="hook_tests", label="Testar hooks de segurança", icon="shield", payload={}),
    ]


async def poll_n8n_ticket(client: "httpx.AsyncClient", ticket_id: str, progress_msg) -> dict:
    """Consulta o webhook de status do n8n até o chamado sair de 'processing'."""
    stage_labels = {
        "received": "📥 Chamado registrado — aguardando o Agente 1 (Triagem N1)...",
        "triage_done": "🧠 Triagem concluída — Supervisor/Agente 2 (Remediação N2) em andamento...",
    }
    last_stage = None
    for _ in range(POLL_MAX_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        resp = await client.get(N8N_STATUS_URL, params={"ticket_id": ticket_id})
        if resp.status_code not in (200, 404):
            continue
        data = resp.json()
        status, stage = data.get("status"), data.get("stage")
        if status in ("done", "error"):
            return data
        if stage != last_stage and stage in stage_labels:
            last_stage = stage
            progress_msg.content = f"🎫 Ticket `{ticket_id}`\n\n{stage_labels[stage]}"
            await progress_msg.update()
    return {"status": "timeout", "ticket_id": ticket_id}


if HAS_CHAINLIT:
    @cl.on_chat_start
    async def on_chat_start():
        """Inicializa a sessão conversacional do colaborador."""
        session_id = f"user_session_{uuid.uuid4().hex[:8]}"
        cl.user_session.set("session_id", session_id)

        welcome_message = (
            "### 🤖 Central de Suporte de TI Inteligente (Nível 1)\n\n"
            "Olá! Sou o **Agente de Triagem de TI Corporativo**. Estou conectado à monitoria de infraestrutura, "
            "ao Active Directory e à Base de Conhecimento para diagnosticar seu problema.\n\n"
            "**Como posso ajudar?** Exemplos comuns:\n"
            "- *'Não consigo acessar a folha de pagamento, erro 403. E-mail maria.souza@empresa.com. Urgente até 17h.'*\n"
            "- *'A VPN corporativa está caindo constantemente no gateway principal.'*\n"
            "- *'Meu computador desligou e não acende nenhum LED.'*\n\n"
            "Use os botões abaixo para **verificar os serviços** do pipeline ou **testar os hooks de segurança**.\n\n"
            f"*ID da Sessão Ativa:* `{session_id}`"
        )
        await cl.Message(content=welcome_message, actions=panel_actions()).send()

    @cl.action_callback("check_services")
    async def on_check_services(action: cl.Action):
        await cl.Message(content=await check_services()).send()

    @cl.action_callback("hook_tests")
    async def on_hook_tests(action: cl.Action):
        try:
            content = await asyncio.to_thread(run_hook_tests)
        except Exception as ex:
            content = f"❌ Não foi possível executar os hooks: `{ex}`"
        await cl.Message(content=content).send()

    @cl.action_callback("ticket_status")
    async def on_ticket_status(action: cl.Action):
        try:
            content = await fetch_ticket_status(action.payload["ticket_id"])
        except Exception as ex:
            content = f"❌ Falha ao consultar o n8n: `{ex}`"
        await cl.Message(content=content).send()

    @cl.action_callback("ticket_audit")
    async def on_ticket_audit(action: cl.Action):
        content = await asyncio.to_thread(
            ticket_audit_trail,
            action.payload["ticket_id"],
            action.payload.get("created_at", ""),
            action.payload.get("completed_at", ""),
        )
        await cl.Message(content=content).send()

    @cl.on_message
    async def on_message(message: cl.Message):
        """Processa a mensagem do usuário, aciona o Webhook n8n ou a API do Agente 1 e exibe o resultado."""
        session_id = cl.user_session.get("session_id")
        user_prompt = message.content

        loading_msg = await cl.Message(
            content="🔄 *Encaminhando seu chamado para a esteira assíncrona de triagem do n8n...*"
        ).send()

        result_data = None
        extra_md = ""
        followup_actions = None
        source = "n8n Webhook (assíncrono: 202 + polling de status)"

        # 1. Aciona o Webhook do n8n (Gatilho Principal - Slide 8).
        #    O n8n NÃO espera os agentes: responde 202 + ticket_id imediatamente.
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                n8n_resp = await client.post(
                    N8N_WEBHOOK_URL,
                    json={
                        "user_prompt": user_prompt,
                        "session_id": session_id
                    }
                )
                if n8n_resp.status_code != 202:
                    raise RuntimeError(f"n8n respondeu HTTP {n8n_resp.status_code}")
                ticket_id = n8n_resp.json().get("ticket_id")
                loading_msg.content = (
                    f"✅ **Chamado recebido pelo n8n** (HTTP 202) — ticket `{ticket_id}`.\n\n"
                    "Os agentes estão processando em segundo plano; acompanho o status para você..."
                )
                await loading_msg.update()

                final = await poll_n8n_ticket(client, ticket_id, loading_msg)
                if final.get("status") == "error":
                    loading_msg.content = f"❌ Erro no processamento do ticket `{ticket_id}`: {final.get('error')}"
                    await loading_msg.update()
                    return
                if final.get("status") != "done":
                    loading_msg.content = (
                        f"⏳ O ticket `{ticket_id}` ainda está em processamento. "
                        f"Consulte depois em `{N8N_STATUS_URL}?ticket_id={ticket_id}`."
                    )
                    await loading_msg.update()
                    return

                pipeline = final.get("result") or {}
                result_data = pipeline.get("triage_n1") or {}
                remediation = pipeline.get("remediation_n2") or {}
                sla = pipeline.get("subworkflow_sla") or {}
                supervisor = pipeline.get("supervisor_decision") or {}
                if remediation.get("skipped"):
                    rem_line = "Não necessária (decisão do Supervisor)"
                else:
                    rem_line = f"`{remediation.get('status', '-')}` — {remediation.get('resolution_summary', '-')}"
                extra_md = f"""
---

### 🔧 Agente 2 (Remediação N2) e SLA:
| Atributo | Detalhe |
| :--- | :--- |
| **Ticket:** | `{ticket_id}` |
| **Decisão do Supervisor (n8n):** | {supervisor.get('audit_comment', '-')} |
| **Remediação:** | {rem_line} |
| **SLA:** | `{sla.get('sla_target_minutes', '-')} min` — {sla.get('assigned_team', '-')} (`{sla.get('sla_badge', '-')}`) |
"""
                followup_actions = ticket_actions(
                    ticket_id, final.get("created_at", ""), final.get("completed_at", "")
                )
            except Exception:
                # 2. Fallback transparente para a API REST direta do Agente 1 (caso o n8n não esteja rodando localmente)
                source = "Agente 1 API (Direto com Polling)"
                try:
                    run_resp = await client.post(
                        f"{AGENT1_API_URL}/run",
                        headers=AGENT1_HEADERS,
                        json={
                            "user_prompt": user_prompt,
                            "session_id": session_id
                        }
                    )
                    if run_resp.status_code == 202:
                        task_id = run_resp.json().get("task_id")
                        # Polling assíncrono em /status/{task_id}
                        for _ in range(15):
                            await asyncio.sleep(1.0)
                            status_resp = await client.get(f"{AGENT1_API_URL}/status/{task_id}", headers=AGENT1_HEADERS)
                            if status_resp.status_code == 200:
                                status_data = status_resp.json()
                                if status_data.get("status") == "done":
                                    result_data = status_data.get("result")
                                    break
                                elif status_data.get("status") == "error":
                                    loading_msg.content = f"❌ Erro no processamento: {status_data.get('error')}"
                                    await loading_msg.update()
                                    return
                except Exception as ex:
                    loading_msg.content = (
                            f"⚠️ **Falha de Conexão com os Serviços:**\n\n"
                            f"Não foi possível conectar ao n8n ({N8N_WEBHOOK_URL}) nem à API do Agente 1 ({AGENT1_API_URL}).\n"
                            f"Detalhe: `{ex}`\n\n"
                            f"Certifique-se de que os serviços estão em execução (`uvicorn agent1.app:app --port 8001`)."
                    )
                    await loading_msg.update()
                    return

        if not result_data:
            loading_msg.content = "⚠️ O processamento da triagem excedeu o tempo limite. Tente novamente."
            await loading_msg.update()
            return

        # Formata o retorno estruturado para exibição no Chainlit
        ticket_summary = result_data.get("ticket_summary", "Chamado Triado")
        category = result_data.get("category", "Geral")
        severity = result_data.get("severity", "Media")
        recommended_action = result_data.get("recommended_action", "Aguardar atendimento de suporte.")
        requires_escalation = result_data.get("requires_human_escalation", False)
        reasoning_steps = result_data.get("reasoning_steps", [])
        tools_invoked = result_data.get("tools_invoked", [])
        confidence = result_data.get("confidence_score", 0.95)

        escalation_badge = "🚨 **Sim (Exige N2/N3 ou Intervenção Presencial)**" if requires_escalation else "✅ **Não (Auto-resolução / N1)**"

        steps_formatted = "\n".join([f"{i+1}. {step}" for i, step in enumerate(reasoning_steps)]) or "Raciocínio concluído com sucesso."
        tools_formatted = ", ".join([f"`{t}`" for t in tools_invoked]) or "Nenhuma"

        response_md = f"""
## 🎯 Diagnóstico de Suporte de TI Concluído

**Origem do Processamento:** `{source}`
**Sessão SQLite:** `{session_id}`

| Atributo | Detalhe |
| :--- | :--- |
| **Resumo:** | {ticket_summary} |
| **Categoria:** | `{category}` |
| **Severidade:** | `{severity}` |
| **Escalonamento Humano:** | {escalation_badge} |
| **Confiança do Modelo:** | `{confidence * 100:.1f}%` |

---

### 💡 Procedimento Recomendado:
{recommended_action}

---

### 🧠 Raciocínio Chain-of-Thought (4 Etapas):
{steps_formatted}

---

### 🛠️ Ferramentas Consultadas:
{tools_formatted}
{extra_md}"""
        loading_msg.content = response_md
        await loading_msg.update()

        if followup_actions:
            await cl.Message(
                content="**O que deseja ver sobre este chamado?**",
                actions=followup_actions,
            ).send()


else:
    def main():
        print("Para executar o Chatbot Corporativo, instale o Chainlit:")
        print("  pip install chainlit")
        print("E inicie com:")
        print("  chainlit run chatbot/app.py -w")

    if __name__ == "__main__":
        main()
