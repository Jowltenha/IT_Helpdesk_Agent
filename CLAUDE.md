# IT Helpdesk Agent - Guia do Claude Code

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

---

## 🛠️ Comandos Frequentes de Execução

- **Executar o Agente Principal (Main Runner TP2):**
  `python agent/main.py`
- **Executar o Pipeline de Prompt Chaining (4 etapas):**
  `python prompts/prompt_chaining.py`
- **Executar a Avaliação A/B de Prompts (Benchmark):**
  `python evaluation/evaluate.py`
- **Ativar o Ambiente Virtual:**
  `source .venv/bin/activate`

---

## 📁 Estrutura da Arquitetura do Repositório

- `agent/`: Módulos centrais do agente:
  - `main.py`: Runner principal (integra Tools, SQLiteSession, RAG e Pydantic).
  - `tools.py`: Ferramentas externas decoradas com `@function_tool`.
  - `memory.py`: Persistência relacional de histórico com `SQLiteSession`.
  - `rag.py`: Engine RAG de busca semântica por embeddings (TF-IDF + cosseno).
  - `models.py`: Modelos Pydantic v2 de validação estrita (`HelpdeskResponse`).
  - `execution_log.json`: Logs formatados e tipados de execuções.
- `prompts/`: Decomposição de tarefas em 4 etapas (*Prompt Chaining* & *CoT*).
  - `prompt_helpdesk.md`: Anatomia do prompt principal do TP1/TP2.
  - `prompt_chaining.py`: Script do pipeline de raciocínio encadeado.
  - `prompts_chained_doc.md`: Documentação das 4 etapas de decomposição.
- `evaluation/`: Benchmark automatizado A/B e registro do ciclo Prompt-Response-Reflect-Revise.
- `spec/`: Especificação técnica original do TP1 e atualizada do TP2.
- `RELATORIO_TECNICO.md`: Relatório técnico completo dos entregáveis (slides 52 a 60).

---

## 🐍 Convenções e Tecnologias

- **Python >= 3.10** com **Pydantic v2** para validação estrita de schemas e tipos.
- **OpenAI Python SDK (`AsyncOpenAI`)** com integração ao proxy local **9Router Proxy / Antigravity**.
- Ferramentas externas tipadas decoradas com `@function_tool` compatíveis com o OpenAI Agents SDK.
- Persistência relacional em banco SQLite (`agent_sessions.db`).
- Busca semântica RAG para recuperação procedural da Base de Conhecimento interna.
- Padrão de respostas estritamente validadas em JSON sem invólucros markdown.
