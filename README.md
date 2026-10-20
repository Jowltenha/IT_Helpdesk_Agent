# IT Helpdesk Agent - Arquitetura de Agentes Desacoplados (TP3)

Este repositório contém a evolução completa do projeto de **Agentes de IA para Suporte de TI Corporativo**, contemplando:
- **TP1:** Componente funcional inicial de triagem com Pydantic v2 e cliente assíncrono.
- **TP2:** Protótipo funcional com Tools Python (`@function_tool`), memória relacional SQLite, RAG semântico por embeddings e raciocínio encadeado (*Prompt Chaining* / CoT).
- **TP3:** Transformação em **Microserviços Independentes via FastAPI**, introdução do **Segundo Agente (Remediação N2 / ITSM)**, documentação individual com **CLAUDE.md** sob *Context Engineering*, primeiro workflow **n8n** e consolidação final do pipeline de prompts.

---

## 📁 Estrutura de Diretórios do Projeto (TP3)

```text
IT_Helpdesk_Agent/
├── agent1/                         # AGENTE 1: Triagem de Suporte de TI N1 (Porta 8001)
│   ├── app.py                      # FastAPI App (POST /run 202, GET /status/{task_id}, GET /health)
│   ├── runner.py                   # HelpdeskAgentRunner assíncrono (LLM, Tools, RAG, Memória)
│   ├── models.py                   # Pydantic v2: RunRequest, HelpdeskResponse, TaskStatusResponse
│   ├── tools.py                    # Ferramentas (@function_tool): check_system_status, lookup_user, KB
│   ├── memory.py                   # SQLiteSession (agent1_sessions.db)
│   ├── rag.py                      # VectorEmbeddingRAG (TF-IDF + Similaridade de Cosseno)
│   ├── test_agent1_api.py          # Testes automatizados da API do Agente 1
│   └── CLAUDE.md                   # Context Engineering: Hierarchical Context Layering
│
├── agent2/                         # AGENTE 2: Auto-Remediação e Despacho N2 (Porta 8002)
│   ├── app.py                      # FastAPI App (POST /run 202, GET /status/{task_id}, GET /health)
│   ├── runner.py                   # RemediationAgentRunner assíncrono
│   ├── models.py                   # Pydantic v2: RemediationRequest, RemediationResponse, TaskStatus
│   ├── tools.py                    # Ferramentas: unlock_user_account, vpn_failover, dispatch_sla
│   ├── test_agent2_api.py          # Testes automatizados da API do Agente 2
│   └── CLAUDE.md                   # Context Engineering: Inverted Pyramid & Constraint Anchoring
│
├── workflows/                      # Integração com n8n
│   ├── tp3_agent1_trigger_workflow.json  # Workflow exportado em JSON pronto para importação
│   └── README.md                   # Guia passo a passo de importação e execução no n8n
│
├── integration/                    # Contratos de API e Orquestração Futura
│   └── api_contract.md             # Contrato de API REST dos dois agentes e plano para TP4
│
├── evaluation/                     # Avaliação Consolidada do Pipeline de Prompts
│   ├── evaluate.py                 # Benchmark automatizado das 3 variantes (A, B e C)
│   ├── eval_results_final.json     # Resultados numéricos da avaliação comparativa
│   └── final_prompt_evaluation.md  # Relatório analítico, justificativa técnica e diagnóstico de prompt ineficaz
│
├── RELATORIO_TECNICO_TP3.md        # Relatório Técnico Completo de Entrega do TP3
├── RELATORIO_TECNICO.md            # Relatório Técnico do TP2 (Arquivo Histórico)
└── README.md                       # Documentação principal
```

---

## ⚙️ Como Executar os Agentes e Testes Localmente

### 1. Ativar o Ambiente Virtual
```bash
source .venv/bin/activate
```

### 2. Executar o Agente 1 (Triagem N1 - Porta 8001)
```bash
# Iniciar o servidor HTTP FastAPI:
uvicorn agent1.app:app --host 0.0.0.0 --port 8001 --reload

# Em outro terminal, executar a suíte de testes automatizados da API:
python agent1/test_agent1_api.py
```

### 3. Executar o Agente 2 (Auto-Remediação N2 - Porta 8002)
```bash
# Iniciar o servidor HTTP FastAPI:
uvicorn agent2.app:app --host 0.0.0.0 --port 8002 --reload

# Em outro terminal, executar a suíte de testes automatizados da API:
python agent2/test_agent2_api.py
```

### 4. Executar o Benchmark Final de Avaliação de Prompts
```bash
python evaluation/evaluate.py
```

---

## 🌐 Testando os Endpoints via cURL

### Agente 1: Disparo de Triagem Assíncrona
```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{
    "user_prompt": "Não consigo acessar a folha de pagamento. Erro 403. E-mail maria.souza@empresa.com. Urgente até 17h.",
    "session_id": "sessao_demo_curl"
  }'
```
*Retorno imediato (202 Accepted):*
```json
{
  "task_id": "task_a1b2c3d4e5f6",
  "status": "pending",
  "message": "Chamado recebido com sucesso. Processamento de triagem iniciado em background."
}
```

*Consulta de status e resultado:*
```bash
curl -X GET http://localhost:8001/status/task_a1b2c3d4e5f6
```

---

### Agente 2: Disparo de Auto-Remediação
```bash
curl -X POST http://localhost:8002/run \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TCK-40301-BR",
    "user_email": "maria.souza@empresa.com",
    "category": "Acessos/Senhas",
    "severity": "Alta",
    "recommended_action": "Solicitar desbloqueio da conta no Active Directory.",
    "requires_human_escalation": false,
    "action_type": "UNLOCK_ACCOUNT"
  }'
```

*Consulta de status e auditoria:*
```bash
curl -X GET http://localhost:8002/status/rem_task_1a2b3c4d5e6f
```

---

## 🔄 Importação do Workflow no n8n

1. Certifique-se de que o **Agente 1** está ativo na porta `8001`.
2. Abra o **n8n** no navegador (`http://localhost:5678`).
3. Vá em **Workflows** -> **Import from File...** e selecione `workflows/tp3_agent1_trigger_workflow.json`.
4. Clique em **"Test workflow"** para ver o acionamento via nó HTTP e a captura da resposta em tempo real.

---

## 📑 Entregáveis do TP3

- **Relatório Técnico do TP3:** [`RELATORIO_TECNICO_TP3.md`](RELATORIO_TECNICO_TP3.md)
- **Contrato de API e Integração:** [`integration/api_contract.md`](integration/api_contract.md)
- **Avaliação Final e Diagnóstico de Prompts:** [`evaluation/final_prompt_evaluation.md`](evaluation/final_prompt_evaluation.md)
- **CLAUDE.md do Agente 1:** [`agent1/CLAUDE.md`](agent1/CLAUDE.md)
- **CLAUDE.md do Agente 2:** [`agent2/CLAUDE.md`](agent2/CLAUDE.md)
