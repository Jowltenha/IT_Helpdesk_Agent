# CLAUDE.md - Agent 1: Agente de Triagem de Suporte de TI N1 (TP4)

## 📌 Context Engineering Strategy: Hierarchical Layering & Formal Specification
Este arquivo implementa a estratégia de **Hierarchical Context Layering (Camadas Hierárquicas de Contexto)** e atua como a **fonte única da verdade (Single Source of Truth)** para o desenvolvimento, governança e operação do **Agente 1**. As diretrizes são organizadas em camadas com precedência estrita:
1. **Camada 0 (Missão, Escopo e Fronteiras):** Papel exclusivo e isolamento funcional do agente.
2. **Camada 1 (Arquitetura e Hierarquia de Arquivos):** Estrutura interna de código, hooks, skills e subagentes.
3. **Camada 2 (Protocolo de Ferramentas, RAG e Hooks):** Contrato de execução de `@function_tool`, hook `PreToolUse` e RAG vetorial.
4. **Camada 3 (Endpoints REST e Ciclo de Vida Assíncrono):** Contrato HTTP via FastAPI (`POST /run` e `GET /status/{task_id}`).
5. **Camada 4 (Governança, Permissões e Subagentes):** Regras de `settings.json`, isolamento de contexto do subagente e skill `SKILL.md`.
6. **Camada 5 (Mapeamento de Requisitos e Rastreabilidade):** Tabela de correspondência entre os requisitos do projeto e as entregas.

---

## 🎯 Camada 0: Missão, Escopo e Responsabilidade

O **Agent 1** é responsável **estritamente pela triagem inicial, diagnóstico e classificação de chamados corporativos de TI (Nível 1)**.
- **O que faz:**
  - Analisa descrições de problemas enviadas por colaboradores em linguagem natural livre.
  - Intercepta invocações com o hook `PreToolUse` (`pre_tool_validator.py`) para validação e sanitização de argumentos.
  - Consulta o estado de sistemas corporativos (`check_system_status`).
  - Consulta contas e grupos no Active Directory (`lookup_user_account`).
  - Recupera procedimentos operacionais da Base de Conhecimento com busca densa vetorial (`VectorEmbeddingRAG`).
  - Executa raciocínio em etapas (Chain-of-Thought) para sintetizar severidade, categoria e determinar se o chamado exige escalonamento humano para N2/N3 (`requires_human_escalation`).
  - Delega pesquisas aprofundadas ao subagente especializado `kb-researcher`.
- **O que NÃO faz:**
  - Não executa remediações, alterações no Active Directory ou failover de rede (responsabilidade exclusiva do Agent 2).
  - Não se comunica diretamente com o Agent 2. Toda a orquestração e passagem de contexto é mediada externamente pelo **n8n**.

---

## 📁 Camada 1: Estrutura e Hierarquia de Arquivos do Agente 1

```
agent1/
├── app.py                      # FastAPI: endpoints assíncronos POST /run, GET /status/{task_id}, GET /health (Porta 8001)
├── runner.py                   # HelpdeskAgentRunner: orquestração via OpenAI Agents SDK (Agent + Runner)
├── models.py                   # Modelos Pydantic v2 estritos: RunRequest, TaskStatusResponse, HelpdeskResponse
├── tools.py                    # Ferramentas Python externas (@function_tool) com interceptação de Hook
├── memory.py                   # Persistência de sessões multi-turnos via SQLiteSession oficial do SDK (agent1_sessions.db)
├── rag.py                      # Motor RAG por similaridade de cosseno com embeddings vetoriais densos (1536 dimensões)
├── mcp_server.py               # Servidor MCP oficial expondo ferramentas do agente via stdio (#Req 6 Slide 8)
├── settings.json               # Especificação formal de permissões (allow, deny, ask) e registro de hooks
├── SKILL.md                    # Skill reutilizável de Procedimento Operacional: active-directory-diagnostics
├── hooks/
│   ├── pre_tool_validator.py   # Hook PreToolUse: sanitização de entrada, validação de e-mails e logging
│   ├── test_hook.py            # Testes automatizados verificáveis do hook
│   └── hook_audit.log          # Log de auditoria gerado pelo hook
├── subagents/
│   └── kb_researcher.md        # Subagente com isolamento de contexto para pesquisa de SOPs
├── test_agent1_api.py          # Suíte de testes HTTP automatizados da API REST
├── execution_log.json          # Registro real de execuções (sem mocks pré-fabricados)
├── AGENTS.md                   # Especificação técnica do agente para o ecossistema de desenvolvimento
└── CLAUDE.md                   # Fonte única de verdade e diretrizes técnicas do Agente 1
```

---

## 🛠️ Camada 2: Protocolo de Ferramentas, Hooks e RAG

### 1. Hook Interceptor `PreToolUse` (`hooks/pre_tool_validator.py`):
- Executado automaticamente antes de qualquer chamada a `@function_tool`.
- **Comportamento Verificável:**
  - Valida se o parâmetro `user_email` possui sintaxe válida e domínio corporativo `@empresa.com`.
  - Bloqueia injeção de comandos ou caracteres especiais (`;`, `|`, `&`, `$`).
  - Registra cada tentativa (permitida ou bloqueada) com timestamp ISO 8601 em `hooks/hook_audit.log`.

### 2. Ferramentas Python (`tools.py`):
- `check_system_status(service_name: str) -> str`: Retorna status operacional JSON de serviços monitorados (`vpn`, `folha`/`payroll`, `email`, `erp`).
- `lookup_user_account(user_email: str) -> str`: Retorna perfil, grupos e indicador crítico `account_locked: bool` do Active Directory.
- `query_troubleshooting_kb(query: str) -> str`: Recupera procedimentos operacionais da Base de Conhecimento (`KB-101` a `KB-104`).

### 3. RAG Semântico Vetorial (`rag.py`):
- Utiliza a classe `VectorEmbeddingRAG` com embeddings vetoriais densos de 1536 dimensões e cálculo de similaridade de cosseno.
- Injeta os procedimentos mais relevantes na seção `--- CONTEXTO PROCEDURAL (RAG KB RETRIEVAL) ---` das instruções do agente.

### 4. Memória Persistente de Sessão (`memory.py`):
- Implementada via `agents.memory.SQLiteSession` oficial do SDK (`agent1_sessions.db`).
- Mantém o histórico conversacional indexado pelo `session_id`.

---

## 🌐 Camada 3: Endpoints REST e Ciclo de Vida Assíncrono (Porta 8001)

### 1. `POST /run` (Status: `202 Accepted`):
- Recebe payload JSON `RunRequest` (`user_prompt` e `session_id`).
- Retorna imediatamente `TaskInitiatedResponse` com `task_id` gerado via UUID.
- Processa a inferência e execução de ferramentas em background via FastAPI `BackgroundTasks`.

### 2. `GET /status/{task_id}`:
- Estados: `pending`, `done`, `error`.
- Ao concluir, retorna `TaskStatusResponse` contendo o laudo estruturado tipado em `HelpdeskResponse`.

---

## 🛡️ Camada 4: Governança, Permissões e Subagentes

### 1. Matriz de Permissões (`settings.json`):
- **`allow`:** Leitura de arquivos internos, execução de testes unitários (`pytest`, `test_agent1_api.py`, `test_hook.py`) e gravação em arquivos de log dedicados (`execution_log.json`, `hook_audit.log`).
- **`deny`:** Comandos destrutivos no terminal (`rm -rf`, `git push --force`, `drop database`, remoção de `agent1_sessions.db`).
- **`ask`:** Modificações estruturais em schemas Pydantic (`models.py`), scripts centrais (`runner.py`, `app.py`) e manipulação direta via SQL no banco de sessões.

### 2. Skill Reutilizável (`SKILL.md`):
- **Nome:** `active-directory-diagnostics`.
- Encapsula o Procedimento Operacional Padrão para diagnóstico de bloqueios no Active Directory, erros 403 e validação de grupos de acesso.

### 3. Subagente Especialista (`subagents/kb_researcher.md`):
- **Nome:** `kb-researcher` | **Modelo:** `ag/claude-sonnet-4-6`.
- **Ferramentas:** `query_troubleshooting_kb`, `check_system_status`.
- **Justificativa de Isolamento:** Artigos de procedimentos técnicos são extensos e detalhados. O subagente pesquisa os artigos em contexto separado e sintetiza apenas os passos acionáveis, evitando a saturação da janela de contexto do agente principal.

---

## 📊 Camada 5: Mapeamento de Requisitos e Rastreabilidade

| Requisito do Projeto | Componente / Implementação | Estado Atual no TP4 |
| :--- | :--- | :---: |
| **Dois Agentes Desacoplados** | `agent1/` (porta 8001) e `agent2/` (porta 8002) | ✅ Concluído |
| **Core com OpenAI Agents SDK** | `Agent`, `Runner`, `@function_tool`, `output_type=HelpdeskResponse` | ✅ Concluído |
| **Memória Persistente Oficial** | `agents.memory.SQLiteSession` (`agent1_sessions.db`) | ✅ Concluído |
| **RAG por Embeddings Vetoriais** | Vetores densos de 1536 dimensões + Similaridade de Cosseno | ✅ Concluído |
| **API REST Assíncrona** | `POST /run` (202) e `GET /status/{task_id}` via BackgroundTasks | ✅ Concluído |
| **Servidor MCP** | `agent1/mcp_server.py` com protocolo stdio | ✅ Concluído |
| **Especificação de Permissões** | `agent1/settings.json` com regras `allow`, `deny` e `ask` | ✅ Concluído |
| **Hooks Automatizados** | Hook `PreToolUse` (`hooks/pre_tool_validator.py`) com auditoria | ✅ Concluído |
| **Skills Reutilizáveis** | `agent1/SKILL.md` (`active-directory-diagnostics`) | ✅ Concluído |
| **Subagentes Isolados** | `agent1/subagents/kb_researcher.md` com justificativa formal | ✅ Concluído |
| **Orquestração n8n Completa** | `workflows/tp4_main_orchestration_workflow.json` com Polling e Merge | ✅ Concluído |
