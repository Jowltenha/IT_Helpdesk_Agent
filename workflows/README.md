# Workflows n8n - Integracao com os Agentes de TI (TP3)

Este diretorio contem o primeiro workflow funcional do **n8n** desenvolvido para disparar o **Agente 1 (Triagem de TI N1)** e capturar sua resposta estruturada.

---

## 📁 Arquivos deste Diretorio

- `tp3_agent1_trigger_workflow.json`: Exportacao oficial do workflow em formato JSON compativel com o n8n.

---

## 🛠️ Como Importar e Executar no n8n

1. **Inicie o Agente 1 localmente:**
   ```bash
   # No terminal integrado do Antigravity
   uvicorn agent1.app:app --host 0.0.0.0 --port 8001
   ```

2. **Abra o n8n no navegador:**
   - Acesse `http://localhost:5678` (ou a URL da sua instancia do n8n).

3. **Importe o Workflow:**
   - No menu lateral do n8n, clique em **Workflows** -> **Add Workflow** (ou `...` no canto superior direito).
   - Selecione **Import from File...** e aponte para o arquivo `workflows/tp3_agent1_trigger_workflow.json`.

4. **Execute o Teste:**
   - Clique no botao **"Test workflow"** (ou no no inicial *"When clicking ‘Execute workflow’"*).
   - O n8n executara o fluxo sequencial:
     1. **Set Ticket Data:** Define o texto do chamado corporativo e o ID da sessao.
     2. **HTTP Request - Trigger Agent 1:** Envia `POST http://localhost:8001/run` e recebe imediatamente `HTTP 202 Accepted` com `task_id`.
     3. **Wait for Agent Execution:** Pausa o fluxo por 2 segundos para processamento em background da LLM, ferramentas e RAG.
     4. **HTTP Request - Poll Agent 1 Status:** Consulta `GET http://localhost:8001/status/{{task_id}}` e recebe o `result` tipado com `HelpdeskResponse`.
     5. **Format Agent 1 Output:** Extrai os campos `ticket_summary`, `category`, `severity`, `recommended_action` e `requires_human_escalation`.

---

## 🚀 Projecao para o TP4: Orquestracao Completa de Agentes

No **TP4**, este workflow sera estendido para implementar a orquestracao deterministica completa entre o **Agent 1 (Triagem)** e o **Agent 2 (Remediacao N2)**:
- Um no condicional **If / Switch** avaliara se `requires_human_escalation == true` ou se o problema envolve credenciais/redes.
- Em caso afirmativo, o n8n disparara `POST http://localhost:8002/run` no **Agent 2**, repassando o e-mail e a categoria para execucao da auto-remediacao (desbloqueio de AD ou failover de VPN) sem qualquer dependencia direta entre os codigos de ambos os agentes.
