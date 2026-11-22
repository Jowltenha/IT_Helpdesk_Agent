# IT Helpdesk Agent - Guia do Claude Code

## ⚠️ Regras obrigatórias para relatórios e entregas

- **SEMPRE** coloque o link do repositório GitHub no **topo** de qualquer relatório, roteiro ou documento de entrega gerado (arquivos em `relatorios/`, README, notas para o Obsidian etc.):
  `> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent`
  - Em arquivos com frontmatter YAML (notas do Obsidian), coloque o link logo **após** o bloco `---` final, para não quebrar o frontmatter.
- Roteiros pessoais de gravação de vídeo (`relatorios/ROTEIRO_VIDEO_*.md`) são material de apoio e ficam no `.gitignore`.
- O n8n roda em Docker (`n8n-dev`): de dentro dele, os agentes são acessados por `http://local:8001` / `http://local:8002` (e não por `localhost`).

## 📌 Visão Geral e Histórico do Projeto

Este repositório contém o **Agente Inteligente de Triagem de Suporte de TI Nível 1**, desenvolvido como Projeto de Bloco. O projeto evoluiu em duas etapas principais:

### 🔹 TP1 (Primeira Etapa - Componente Funcional Inicial):
- **Definição do Problema:** Automatação da triagem inicial de chamados corporativos de suporte N1 (hardware, software, acessos, VPN).
- **Arquitetura Inicial:** Cliente `AsyncOpenAI` conectado ao proxy local (**9Router Proxy / Antigravity**) utilizando o modelo `ag/claude-sonnet-4-6`.
- **Anatomia de Prompt:** Estruturado em 4 componentes obrigatórios (Instrução, Contexto, Exemplos Few-Shot e Restrições de Saída).
- **Saída Estruturada Inicial:** Validação com **Pydantic v2** (`HelpdeskResponse`) para retorno estrito de JSON sem markdown.

### 🔹 TP2 (Segunda Etapa - Protótipo Funcional Completo):
- **Ferramentas Python Externas (`@function_tool`):** Acesso a dados de infraestrutura (`check_system_status`), Active Directory (`lookup_user_account`) e base de suporte (`query_troubleshooting_kb`).
- **Memória Persistente de Sessão (`SQLiteSession`):** Histórico de conversas retido no banco relacional `agent_sessions.db` para continuidade entre chamadas.
- **RAG Semântico por Embeddings (`VectorEmbeddingRAG`):** Recuperação de artigos procedimentos da Base de Conhecimento por similaridade de cosseno.
- **Decomposição em Etapas (`Prompt Chaining` & CoT):** Decomposição em 4 passos (*Least-to-Most Prompting*) para análise profunda de causa raiz.
- **Avaliação A/B e Métricas de Qualidade:** Benchmark automatizado com salto de desempenho de 55/100 (baseline) para 98.3/100 (refinado).

### 🔹 TP3 e TP4 (Agentes desacoplados e orquestração n8n):
- Dois microserviços FastAPI independentes: `agent1/` (Triagem N1, porta 8001) e `agent2/` (Remediação N2, porta 8002), ambos com `POST /run` (202) e `GET /status/{task_id}`.
- Workflow n8n assíncrono (202 imediato + polling Wait → GET /status → Switch), Supervisor (AI Agent node), sub-workflow de SLA, Merge e chatbot Chainlit como gatilho.
- Governança por agente: `settings.json`, hooks PreToolUse/PostToolUse, `SKILL.md` e subagentes.

### 🔹 TP5 (Qualidade, contratos e operação):
- Cada agente tem seu próprio `CLAUDE.md`, `AGENTS.md`, `TASK.md` e `TOOLS.md`. **Ao trabalhar dentro de `agent1/` ou `agent2/`, siga o `CLAUDE.md` daquela pasta.**
- Servidor MCP do Agente 1: `agent1/mcp/server.py` (FastMCP + schemas Pydantic).
- n8n: Error Workflow (`TP5 - Error Handler`), config na Data Table `helpdesk_config`, segredos em credenciais (X-API-Key).
- Testes regressivos: `tests/` (`python tests/run_regression.py --with-outage`).
- RAG com embeddings reais `gemini-embedding-001` (1536 dimensões) — o TF-IDF do TP2 foi removido.

---

## 🛠️ Comandos Frequentes de Execução

- **Subir os agentes (TP3+):**
  `uvicorn agent1.app:app --port 8001` e `uvicorn agent2.app:app --port 8002`
- **Testes offline dos dois agentes:**
  `python -m pytest agent1/test_agent1_unit.py agent2/test_agent2_unit.py -q`
- **Testes regressivos ponta a ponta (n8n):**
  `python tests/run_regression.py --with-outage`
- **Servidor MCP do Agente 1:**
  `python -m agent1.mcp.server`
- **Executar o Agente legado (TP2):**
  `python agent/main.py`
- **Executar o Pipeline de Prompt Chaining (4 etapas):**
  `python prompts/prompt_chaining.py`
- **Executar a Avaliação A/B de Prompts (Benchmark):**
  `python evaluation/evaluate.py`
- **Ativar o Ambiente Virtual:**
  `source .venv/bin/activate`

---

## 📁 Estrutura da Arquitetura do Repositório

- `agent1/`, `agent2/`: os dois agentes independentes (TP3–TP5), cada um com `CLAUDE.md`, `AGENTS.md`, `TASK.md`, `TOOLS.md`.
- `tests/`: testes regressivos ponta a ponta e evidências (`tests/results/`).
- `workflows/`: workflows n8n exportados (TP5: principal, error handler e SLA).
- `agent/`: Agente legado do TP1/TP2 (mantido como histórico):
  - `main.py`: Runner principal (integra Tools, SQLiteSession, RAG e Pydantic).
  - `tools.py`: Ferramentas externas decoradas com `@function_tool`.
  - `memory.py`: Persistência relacional de histórico com `SQLiteSession`.
  - `rag.py`: RAG do TP2 (TF-IDF + cosseno; substituído no `agent1/rag.py` por embeddings reais).
  - `models.py`: Modelos Pydantic v2 de validação estrita (`HelpdeskResponse`).
  - `execution_log.json`: Logs formatados e tipados de execuções.
- `prompts/`: Decomposição de tarefas em 4 etapas (*Prompt Chaining* & *CoT*).
  - `prompt_helpdesk.md`: Anatomia do prompt principal do TP1/TP2.
  - `prompt_chaining.py`: Script do pipeline de raciocínio encadeado.
  - `prompts_chained_doc.md`: Documentação das 4 etapas de decomposição.
- `evaluation/`: Benchmark automatizado A/B e registro do ciclo Prompt-Response-Reflect-Revise.
- `spec/`: Especificação técnica original do TP1 e atualizada do TP2.
- `relatorios/`: Relatórios técnicos de cada TP (`RELATORIO_TECNICO*.md`) e notas para o Obsidian.
- `prints/`: Capturas de tela usadas nos relatórios.

---

## 🐍 Convenções e Tecnologias

- **Python >= 3.10** com **Pydantic v2** para validação estrita de schemas e tipos.
- **OpenAI Python SDK (`AsyncOpenAI`)** com integração ao proxy local **9Router Proxy / Antigravity**.
- Ferramentas externas tipadas decoradas com `@function_tool` compatíveis com o OpenAI Agents SDK.
- Persistência relacional em banco SQLite (`agent_sessions.db`).
- Busca semântica RAG (embeddings `gemini-embedding-001`, 1536 dimensões, cosseno, limiar 0.62) para recuperação procedural da Base de Conhecimento.
- **Sem fallbacks simulados:** falhas viram `status=error` explícito (o professor penalizou respostas prontas no TP2).
- Segredos somente em `.env` (fora do git) e em credenciais do n8n; nunca em código ou JSON de workflow.
- Padrão de respostas estritamente validadas em JSON sem invólucros markdown.
