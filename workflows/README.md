# Workflows n8n - Orquestração Multi-Agente Assíncrona (TP3 & TP4)

Este diretório contém os workflows oficiais do **n8n** para orquestrar de forma desacoplada o **Agente 1 (Triagem N1)** e o **Agente 2 (Auto-Remediação N2)**, integrando **AI Agent Node com LLM e Tool**, **Sub-workflow Reutilizável de SLA** e o **Gatilho Webhook (Chatbot Chainlit)**.

---

## 📁 Workflows Disponíveis

### 1. `tp4_main_orchestration_workflow.json` (Orquestração Completa TP4)
Workflow avançado que orquestra todo o ciclo assíncrono dos dois agentes com componentes de alto nível:
- **Nó 1 (Gatilho):** `Webhook Trigger` conectado ao Chatbot Corporativo Web (Chainlit via `POST /webhook/helpdesk-triage-tp4`).
- **Nó 2 (Invocação Agente 1):** `HTTP Request POST http://localhost:8001/run` (devolve `202 Accepted` + `task_id`).
- **Nó 3 (Pausa Assíncrona):** `Wait Node` (2 segundos de pausa não-bloqueante).
- **Nó 4 (Polling Agente 1):** `HTTP Request GET http://localhost:8001/status/{task_id}` (repete até `status: done`).
- **Nó 5 (Agent Node de Alto Nível):** `AI Agent Node` (`@n8n/n8n-nodes-langchain.agent`) conectado a:
  - **LLM Node:** `OpenAI Chat Model` (`@n8n/n8n-nodes-langchain.lmChatOpenAi`).
  - **Tool Node:** `Custom Tool - IT Policy Checker` (`@n8n/n8n-nodes-langchain.toolCustom`) para consulta de políticas de TI.
  - *Função:* Arbitra sobre a severidade e valida se o Agente 2 deve ser acionado.
- **Nó 6 (Roteamento Condicional):** `If Node` (avalia se a categoria é `Acessos/Senhas` ou `Redes/VPN` demandando remediação).
- **Nó 7 (Invocação Agente 2):** `HTTP Request POST http://localhost:8002/run`.
- **Nó 8 (Pausa Assíncrona):** `Wait Node` (2 segundos).
- **Nó 9 (Polling Agente 2):** `HTTP Request GET http://localhost:8002/status/{task_id}`.
- **Nó 10 (Invocação de Sub-workflow):** `Execute Workflow Node` que dispara o sub-workflow isolado `tp4_subworkflow_sla_calculator`.
- **Nó 11 (Merge de Dados):** `Merge Node` unificando triagem N1, remediação N2 e metadados de SLA.
- **Nó 12 (Resposta):** `Respond to Webhook` devolvendo o payload final estruturado ao Chatbot Chainlit.

---

### 2. `tp4_subworkflow_sla_calculator.json` (Sub-workflow Reutilizável de SLA)
Sub-workflow modular que encapsula a lógica de cálculo de SLA, validação de plantão e prazos contratuais:
- **Nó 1:** `Execute Workflow Trigger` (permite invocação tanto pelo workflow principal quanto de forma 100% isolada).
- **Nó 2:** `Code Node` (JavaScript) que processa a matriz corporativa de SLA:
  - Crítica: 30 minutos
  - Alta: 120 minutos
  - Média: 480 minutos
  - Baixa: 1440 minutos
  - Calcula o deadline exato no formato ISO 8601 (`sla_deadline_iso`).
- **Nó 3:** `If Node` verificando criticidade (SLA <= 60 minutos).
- **Nós 4 e 5:** Sinalização de prioridade (`PAGERDUTY_ALERT_TRIGGERED` ou `STANDARD_QUEUE`).

---

### 3. Workflows Históricos do TP3
- `tp3_full_orchestration_workflow.json`: Orquestração base dos 9 componentes do Slide 8.
- `tp3_agent1_trigger_workflow.json`: Teste unitário isolado da API do Agente 1.

---

## 🛠️ Como Importar e Executar no n8n

1. **Inicie os Dois Agentes FastAPI em Terminais Distintos:**
   ```bash
   # Terminal 1 - Agente 1 (Porta 8001)
   uvicorn agent1.app:app --host 0.0.0.0 --port 8001 --reload

   # Terminal 2 - Agente 2 (Porta 8002)
   uvicorn agent2.app:app --host 0.0.0.0 --port 8002 --reload
   ```

2. **Abra o n8n no Navegador:**
   - Acesse `http://localhost:5678`.

3. **Importe Primeiro o Sub-workflow:**
   - No n8n, vá em **Workflows** -> **Import from File...**
   - Selecione `workflows/tp4_subworkflow_sla_calculator.json`.
   - Salve e ative o sub-workflow (anote o ID gerado se necessário).

4. **Importe o Workflow Principal:**
   - Selecione `workflows/tp4_main_orchestration_workflow.json`.
   - Vincule o nó `Execute Sub-workflow` ao sub-workflow recém-importado.
   - Ative o workflow.

5. **Teste com o Chatbot Chainlit:**
   ```bash
   chainlit run chatbot/app.py -w
   ```
   Envie uma mensagem (ex: *"Conta bloqueada na folha de pagamento para maria.souza@empresa.com"*). O pipeline completo será executado com os nós em verde no n8n!
