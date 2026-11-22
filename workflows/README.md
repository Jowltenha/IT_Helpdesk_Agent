> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# Workflows n8n - Orquestração Multi-Agente Assíncrona (TP3 & TP4)

Workflows do **n8n** que orquestram, de forma desacoplada e **assíncrona**, o **Agente 1 (Triagem N1)** e o **Agente 2 (Remediação N2)**, com um **AI Agent node (Supervisor)**, um **sub-workflow reutilizável de SLA** e o **chatbot Chainlit** como gatilho.

---

## 1. `tp4_main_orchestration_workflow.json` — TP4 - Orquestracao Assincrona Multi-Agente (Helpdesk)

**Ideia central:** o webhook **não espera os agentes**. Ele registra o chamado, responde `202 + ticket_id` na hora e processa tudo em segundo plano. O chatbot acompanha o andamento por um segundo webhook de status.

| Etapa | Nós | Comportamento |
| :--- | :--- | :--- |
| Entrada | `Webhook Chatbot (Novo Chamado)` (POST `/webhook/helpdesk-triage-tp4`) → `Normalizar Chamado` → `Registrar Chamado (processing)` | Gera o `ticket_id` e grava na Data Table `helpdesk_tickets`. |
| **Resposta imediata** | `Responder 202 Imediato ao Chatbot` | Devolve `202 {ticket_id, status:"processing", status_endpoint}`. **O chatbot é liberado aqui.** |
| Agente 1 | `Disparar Agente 1 (POST /run)` → `Aguardar Agente 1 (3s)` → `Consultar Status Agente 1` → `Agente 1 Terminou?` (Switch) | **Laço de polling:** `pendente_volta_ao_wait` volta ao Wait enquanto `status=pending` (até 40×); `concluido` segue; `erro_ou_timeout` vai para a falha. |
| Supervisor | `Agente Supervisor (n8n)` + `Modelo LLM (Proxy 9Router)` + tool `query_support_policy` + `Formato da Decisao` → `Precisa de Remediacao (Agente 2)?` (If) | Terceiro agente: decide `should_remediate` e `target_action`. |
| Agente 2 | `Disparar Agente 2 (POST /run)` → `Aguardar Agente 2 (3s)` → `Consultar Status Agente 2` → `Agente 2 Terminou?` (Switch) | Mesmo laço de polling do Agente 1. |
| **Merge** | `Resposta do Agente 1` → entrada 1; `Resposta do Agente 2` **ou** `Agente 2 Nao Necessario` → entrada 2; `Merge: Respostas dos 2 Agentes` | Junta as respostas dos dois agentes. |
| SLA e final | `Preparar Dados para SLA` → `Executar Sub-workflow de SLA` → `Consolidar Resultado Final` → `Salvar Resultado (done)` | Grava `status=done` e o `result_json`. |
| Falhas | `Preparar Mensagem de Erro` → `Salvar Falha (error)` | Agente fora do ar, `status=error` ou timeout. |
| Consulta | `Webhook Consulta de Status` (GET `/webhook/helpdesk-status?ticket_id=`) → `Buscar Chamado na Tabela` → `Responder Status do Chamado` | Devolve `processing` / `done` (com resultado) / `error` / `not_found` (404). |

URLs dos agentes: `http://local:8001` e `http://local:8002`. O n8n roda no Docker, e `local` aponta para o host.

## 2. `tp4_subworkflow_sla_calculator.json` — TP4 - Sub-workflow: Calculadora de SLA

`Receber Dados do Workflow Principal` (Execute Workflow Trigger) → `Calcular SLA e Equipe` (Code: Crítica 30 / Alta 120 / Média 480 / Baixa 1440 min, equipe, deadline ISO) → `SLA Critico (ate 60 min)?` (If) → `Marcar Urgencia Alta` / `Marcar SLA Normal`.

## 3. Workflows históricos do TP3

- `tp3_full_orchestration_workflow.json`: orquestração base dos 9 componentes do Slide 8.
- `tp3_agent1_trigger_workflow.json`: teste isolado da API do Agente 1.

---

## Como importar e executar

1. Suba os agentes:
   ```bash
   uvicorn agent1.app:app --host 0.0.0.0 --port 8001
   uvicorn agent2.app:app --host 0.0.0.0 --port 8002
   ```
2. No n8n (`http://localhost:5678`), crie a Data Table **`helpdesk_tickets`** com as colunas (todas string): `ticket_id, status, stage, session_id, user_prompt, result_json, error_message, created_at, completed_at`.
3. Importe e **publique** o sub-workflow `tp4_subworkflow_sla_calculator.json`.
4. Importe `tp4_main_orchestration_workflow.json` e faça três ajustes:
   - selecione a Data Table nos nós de Data Table;
   - selecione o sub-workflow no nó *Executar Sub-workflow de SLA*;
   - crie uma credencial **OpenAI API** (chave do 9Router, Base URL `http://local:20128/v1`) e vincule-a ao nó *Modelo LLM (Proxy 9Router)*.

   Depois publique o workflow.
5. Rode o chatbot com `python chatbot/run_chainlit.py run chatbot/app.py -w` ou teste via `curl`:
   ```bash
   curl -X POST http://localhost:5678/webhook/helpdesk-triage-tp4 -H "Content-Type: application/json" \
     -d '{"user_prompt":"Conta bloqueada, erro 403. maria.souza@empresa.com","session_id":"demo"}'
   curl "http://localhost:5678/webhook/helpdesk-status?ticket_id=<ticket_id>"
   ```
