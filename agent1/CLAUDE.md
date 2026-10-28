# CLAUDE.md - Agent 1: Agente de Triagem de Suporte de TI N1

## 📌 Context Engineering Strategy: Hierarchical Layering & Constraint Anchoring
Este arquivo implementa a estrategia de **Hierarchical Context Layering (Camadas Hierarquicas de Contexto)**. As diretrizes sao organizadas em camadas com precedencia estrita:
1. **Camada 0 (Missao e Identidade):** Papel exclusivo e fronteiras de atuacao do agente.
2. **Camada 1 (Arquitetura e Hierarquia de Arquivos):** Estrutura interna e responsabilidade de cada modulo.
3. **Camada 2 (Protocolo de Ferramentas e Fontes de Dados):** Contrato de execucao de `@function_tool` e RAG.
4. **Camada 3 (Endpoints REST e Contrato Assincrono):** Ciclo de vida HTTP via FastAPI (`POST /run` e `GET /status/{task_id}`).
5. **Camada 4 (Schemas Pydantic v2 e Restricoes Negativas):** Guardrails de validacao estrita e regras de saida sem markdown.

---

## 🎯 Camada 0: Missao, Escopo e Responsabilidade

O **Agent 1** e responsavel **estritamente pela triagem inicial, diagnostico e classificacao de chamados corporativos de TI (Nivel 1)**.
- **O que faz:**
  - Analisa descricoes de problemas enviadas por colaboradores (hardware, software, rede/VPN, acessos/senhas).
  - Consulta o estado de sistemas corporativos (`check_system_status`).
  - Consulta contas e grupos no Active Directory (`lookup_user_account`).
  - Recupera procedimentos operacionais da Base de Conhecimento (`VectorEmbeddingRAG`).
  - Realiza raciocinio encadeado (Chain-of-Thought) para sintetizar severidade, categoria e determinar se o chamado exige escalonamento humano para N2/N3 (`requires_human_escalation`).
- **O que NAO faz:**
  - Nao executa remocoes de bloqueio ou alteracoes diretas no Active Directory (funcao do Agent 2).
  - Nao se comunica diretamente com o Agent 2. Toda orquestracao e interacao ocorre exclusivamente via webhook/HTTP mediada pelo **n8n**.

---

## 📁 Camada 1: Estrutura e Hierarquia de Arquivos

```
agent1/
├── app.py              # Aplicacao FastAPI: endpoints POST /run, GET /status/{task_id}, GET /health
├── runner.py           # HelpdeskAgentRunner: orquestracao interna de LLM, RAG, Tools e memoria
├── models.py           # Modelos Pydantic v2: RunRequest, TaskStatusResponse, HelpdeskResponse
├── tools.py            # Ferramentas Python externas (@function_tool)
├── memory.py           # Persistencia de sessoes em SQLite (agent1_sessions.db)
├── rag.py              # Motor RAG por similaridade de cosseno (VectorEmbeddingRAG)
├── test_agent1_api.py  # Suite de testes HTTP automatizados
└── CLAUDE.md           # Contrato de contexto e diretrizes tecnicas do Agent 1
```

---

## 🛠️ Camada 2: Protocolo de Ferramentas e Fontes de Informacao

### 1. Ferramentas Python (`tools.py`):
- `check_system_status(service_name: str) -> str`:
  - Retorna status operacional JSON de servicos monitorados (`vpn`, `folha`/`payroll`, `email`, `erp`).
- `lookup_user_account(user_email: str) -> str`:
  - Retorna perfil, grupos e indicador critico `account_locked: bool` do Active Directory.
- `query_troubleshooting_kb(query: str) -> str`:
  - Recupera artigos procedural da Base de Conhecimento (`KB-40301`, `KB-80802`).

### 2. Base de Conhecimento RAG Semantico (`rag.py`):
- O motor `VectorEmbeddingRAG` utiliza vetorizacao TF-IDF com busca por similaridade de cosseno.
- Recupera os 2 artigos mais relevantes (`top_k=2`) e os formata como secao `--- CONTEXTO PROCEDURAL (RAG KB RETRIEVAL) ---` injetada no prompt.

### 3. Memoria Persistente (`memory.py`):
- Utiliza a classe `SQLiteSession` apontando para `agent1_sessions.db`.
- Isola o historico de interacoes atraves do parametro `session_id`.

---

## 🌐 Camada 3: Endpoints REST e Ciclo de Vida Assincrono

O Agent 1 e exposto na porta **8001** via FastAPI:

### 1. `POST /run`
- **Descricao:** Registra o chamado e inicia o processamento em segundo plano sem bloquear a requisicao HTTP.
- **Status HTTP:** `202 Accepted`
- **Headers:** `Content-Type: application/json`
- **Payload de Entrada (`RunRequest`):**
  ```json
  {
    "user_prompt": "Nao consigo acessar a folha de pagamento. Erro 403. E-mail maria.souza@empresa.com. Urgente ate 17h.",
    "session_id": "sessao_triagem_01"
  }
  ```
- **Resposta Imediata (`TaskInitiatedResponse`):**
  ```json
  {
    "task_id": "task_a1b2c3d4e5f6",
    "status": "pending",
    "message": "Chamado recebido com sucesso. Processamento de triagem iniciado em background."
  }
  ```

### 2. `GET /status/{task_id}`
- **Descricao:** Permite ao consumidor (n8n ou cliente HTTP) consultar o estado da tarefa.
- **Estados Possiveis:**
  - `pending`: A tarefa ainda esta sendo processada pela LLM/RAG/Tools.
  - `done`: Processamento finalizado com sucesso; campo `result` contem o `HelpdeskResponse`.
  - `error`: Falha durante a execucao; campo `error` contem os detalhes tecnicos.
- **Resposta Concluida (`TaskStatusResponse`):**
  ```json
  {
    "task_id": "task_a1b2c3d4e5f6",
    "status": "done",
    "created_at": "2026-10-19T14:00:00Z",
    "completed_at": "2026-10-19T14:00:02Z",
    "result": {
      "ticket_summary": "Erro 403 na folha de pagamento devido a conta bloqueada",
      "category": "Acessos/Senhas",
      "severity": "Alta",
      "recommended_action": "Solicitar desbloqueio da conta maria.souza@empresa.com no Active Directory e validar pertenca ao grupo Folha_Pagamento_Admin.",
      "requires_human_escalation": true,
      "reasoning_steps": [
        "Identificado erro de acesso 403 e urgencia operacional (prazo 17h).",
        "Tool check_system_status consultada: servico de folha operacional.",
        "Tool lookup_user_account retornou account_locked=True para o e-mail.",
        "RAG KB-101 orienta desbloqueio de conta por suporte N2."
      ],
      "tools_invoked": ["check_system_status", "lookup_user_account", "query_troubleshooting_kb"],
      "confidence_score": 0.98
    },
    "error": null
  }
  ```

### 3. `GET /health`
- Retorna `{"status": "ok", "agent": "Agent 1 - Helpdesk N1 Triage", "version": "1.0.0"}`.

---

## 🛡️ Camada 4: Decisoes Tecnicas e Guardrails Pydantic

1. **Uso de FastAPI BackgroundTasks:**
   - Previne timeouts em gateways HTTP (como n8n ou proxies corporativos) ao processar chamadas LLM e buscas vetoriais.
2. **Validacao Rigorosa via Pydantic v2:**
   - O schema `HelpdeskResponse` valida tipos estritos, valores enumerados de severidade e restricoes de pontuacao (`confidence_score` entre 0.0 e 1.0).
3. **Mecanismo de Limpeza e Fallback:**
   - Metodo `_clean_json_string` remove delimitadores markdown ```json caso a LLM os envie.
   - Fallback deterministico implementado para manter os testes funcionais mesmo em ambientes sem conectividade de internet ou proxy inativo.
4. **Isolamento Completo:**
   - Este agente desconhece a existencia do Agent 2. Qualquer integracao posterior sera orquestrada no n8n.
