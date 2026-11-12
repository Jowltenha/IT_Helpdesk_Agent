"""
Chatbot Corporativo de Autoatendimento de TI em Chainlit.
Atende ao Requisito 9 do Projeto (Slide 8):
"Gatilho (trigger) que dispara o workflow n8n — Escolha única: Chatbot Corporativo Web via Webhook"

Interface conversacional para colaboradores reportarem incidentes em linguagem natural,
mantendo o session_id persistente para a SQLiteSession e acionando o Webhook do n8n.
"""
import os
import uuid
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

try:
    import chainlit as cl
    HAS_CHAINLIT = True
except ImportError:
    HAS_CHAINLIT = False

# Configurações de endpoints
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/helpdesk-triage")
AGENT1_API_URL = os.getenv("AGENT1_API_URL", "http://localhost:8001")


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
            f"*ID da Sessão Ativa:* `{session_id}`"
        )
        await cl.Message(content=welcome_message).send()

    @cl.on_message
    async def on_message(message: cl.Message):
        """Processa a mensagem do usuário, aciona o Webhook n8n ou a API do Agente 1 e exibe o resultado."""
        session_id = cl.user_session.get("session_id")
        user_prompt = message.content

        loading_msg = await cl.Message(
            content="🔄 *Encaminhando seu chamado para a esteira assíncrona de triagem do n8n...*"
        ).send()

        result_data = None
        source = "n8n Webhook"

        # 1. Tenta acionar o Webhook do n8n (Gatilho Principal - Slide 8)
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                n8n_resp = await client.post(
                    N8N_WEBHOOK_URL,
                    json={
                        "user_prompt": user_prompt,
                        "session_id": session_id
                    }
                )
                if n8n_resp.status_code in (200, 201):
                    result_data = n8n_resp.json()
            except Exception:
                # 2. Fallback transparente para a API REST direta do Agente 1 (caso o n8n não esteja rodando localmente)
                source = "Agente 1 API (Direto com Polling)"
                try:
                    run_resp = await client.post(
                        f"{AGENT1_API_URL}/run",
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
                            status_resp = await client.get(f"{AGENT1_API_URL}/status/{task_id}")
                            if status_resp.status_code == 200:
                                status_data = status_resp.json()
                                if status_data.get("status") == "done":
                                    result_data = status_data.get("result")
                                    break
                                elif status_data.get("status") == "error":
                                    await loading_msg.update(content=f"❌ Erro no processamento: {status_data.get('error')}")
                                    return
                except Exception as ex:
                    await loading_msg.update(
                        content=(
                            f"⚠️ **Falha de Conexão com os Serviços:**\n\n"
                            f"Não foi possível conectar ao n8n ({N8N_WEBHOOK_URL}) nem à API do Agente 1 ({AGENT1_API_URL}).\n"
                            f"Detalhe: `{ex}`\n\n"
                            f"Certifique-se de que os serviços estão em execução (`uvicorn agent1.app:app --port 8001`)."
                        )
                    )
                    return

        if not result_data:
            await loading_msg.update(content="⚠️ O processamento da triagem excedeu o tempo limite. Tente novamente.")
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
"""
        await loading_msg.update(content=response_md)


else:
    def main():
        print("Para executar o Chatbot Corporativo, instale o Chainlit:")
        print("  pip install chainlit")
        print("E inicie com:")
        print("  chainlit run chatbot/app.py -w")

    if __name__ == "__main__":
        main()
