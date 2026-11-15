---
title: "Resumo dos 9 Componentes do Sistema - IT Helpdesk Agent"
date: 2026-11-10
author: "João Pedro Barboza"
project: "IT Helpdesk Agent"
status: "Concluído"
tags:
  - obsidian
  - arquiteura-agentes
  - slide-8
  - rubrica-12
  - helpdesk-ai
aliases:
  - "Resumo Componentes Slide 8"
  - "Guia Rápido dos Agentes"
---

# 🚀 Resumo Executivo: Os 9 Componentes de Arquitetura (Slide 8)

> [!TIP] Objetivo
> Visão condensada dos 9 componentes implementados para o trabalho de Helpdesk de TI, em conformidade estrita com a **Rubrica 12** e os apontamentos de melhoria do professor.

---

## 🏛️ Tabela Síntese dos 9 Componentes

| # | Componente | Papel no Sistema | Arquivo / Tecnologia |
| :-: | :--- | :--- | :--- |
| **1** | **Dois Agentes Python Desacoplados** | Agente 1 (Triagem N1) e Agente 2 (Auto-Remediação N2 / Despacho). | `agent1/` (porta 8001) e `agent2/` (porta 8002) |
| **2** | **Memória Persistente (`SQLiteSession`)** | Histórico multi-turnos da conversa indexado por `session_id` (**apenas no Agente 1**). | `agent1/memory.py` (`agents.memory.SQLiteSession`) |
| **3** | **RAG Semântico por Embeddings** | Recuperação de artigos SOP procedurais por similaridade de cosseno (sem TF-IDF). | `agent1/rag.py` (`VectorEmbeddingRAG` - 1536 dimensões) |
| **4** | **APIs REST Assíncronas** | Endpoints de não-bloqueio: `POST /run` (retorna `202 Accepted` + `task_id`) e `GET /status/{task_id}`. | FastAPI + `BackgroundTasks` em ambos os agentes |
| **5** | **Workflow n8n com Polling** | Dispara `/run`, aguarda 2s (Wait Node) e consulta `/status` até `status: done`. | `workflows/tp3_full_orchestration_workflow.json` |
| **6** | **Servidor MCP** | Expõe as ferramentas de triagem (`check_system_status`, `lookup_user`, `query_kb`) via protocolo MCP. | `agent1/mcp_server.py` (`mcp.server.mcpserver.MCPServer`) |
| **7** | **Orquestração e Roteamento n8n** | Nós If/Switch que avaliam a triagem, disparam o Agente 2 se necessário e unem os dados via Merge Node. | Nós de lógica e `Merge` no n8n |
| **8** | **Terceiro Agente no n8n (Agent Node)** | Agente cognitivo interno ao n8n que atua como classificador semântico e redige o parecer de merge. | Nó `@n8n/n8n-nodes-langchain.agent` no workflow |
| **9** | **Gatilho Único Oficial** | Chatbot corporativo Web que repassa o `user_prompt` e `session_id` via Webhook HTTP ao n8n. | `chatbot/app.py` (**Chainlit**) |

---

## 🔍 Detalhamento Direto de Cada Componente

### 1️⃣ Dois Agentes Independentes (`agent1/` e `agent2/`)
- **Agente 1 (Porta 8001):** Recebe o relato livre do usuário, analisa infraestrutura e Active Directory, consulta a base de conhecimento via RAG e classifica severidade e categoria.
- **Agente 2 (Porta 8002):** Recebe parâmetros técnicos estruturados do chamado triado e executa:
  - Desbloqueio de credenciais no AD (`unlock_user_account`).
  - Failover de gateway de VPN (`configure_vpn_failover_route`).
  - Despacho de chamado para N2/N3 com computação de SLA (`dispatch_sla_incident`).
- **Eliminação de Mocks:** Ambos utilizam o core oficial do **OpenAI Agents SDK** e gravam a execução real em `execution_log.json`.

---

### 2️⃣ Memória Persistente de Sessão (`agent1/memory.py`)
- Empregada exclusivamente no **Agente 1**.
- Utiliza a classe oficial `agents.memory.SQLiteSession` do SDK conectada ao banco `agent1/agent1_sessions.db`.
- Garante retenção de contexto para chamados com múltiplos passos sem esquecimento de histórico.

---

### 3️⃣ RAG por Embeddings Vetoriais Densos (`agent1/rag.py`)
- Substituiu completamente o método léxico TF-IDF.
- Gera vetores densos semânticos de 1536 dimensões e aplica similaridade de cosseno.
- Busca procedimentos operacionais da Base de Conhecimento (erros 403, falhas de VPN, substituição de hardware).

---

### 4️⃣ APIs REST Assíncronas (`/run` e `/status`)
- Ambos os serviços FastAPI expõem o contrato:
  - `POST /run`: Devolve resposta HTTP `202 Accepted` contendo `task_id` imediato.
  - `GET /status/{task_id}`: Permite ao orquestrador verificar se a tarefa está `pending`, `done` ou `error`.
- Evita perda de conexão ou timeout em requisições demoradas.

---

### 5️⃣ Polling Assíncrono no n8n
- Padrão não-bloqueante no workflow do n8n:
  - Executa `POST /run` no Agente 1.
  - Pausa por 2 segundos via **Wait Node**.
  - Executa `GET /status/{task_id}` em loop até que o status seja `done`.

---

### 6️⃣ Servidor MCP (`agent1/mcp_server.py`)
- Implementado com a biblioteca oficial `mcp.server.mcpserver`.
- Expõe para ferramentas como Claude Desktop e orquestradores as funções:
  - `check_system_status`
  - `lookup_user_account`
  - `query_troubleshooting_kb`

---

### 7️⃣ Roteamento e Merge no n8n
- Se o Agente 1 classificar o incidente como `Acessos/Senhas` ou `Redes/VPN`, o n8n direciona o fluxo para o Agente 2.
- Um nó **Merge** unifica o diagnóstico inicial do Agente 1 com as ações de remediação e o cálculo de SLA do Agente 2 antes de responder.

---

### 8️⃣ Terceiro Agente Cognitivo no n8n (Agent Node)
- Localizado no meio do workflow do n8n (nó `@n8n/n8n-nodes-langchain.agent`).
- Atua como juiz classificador: analisa o laudo do Agente 1, define a necessidade real de auto-remediação e sintetiza a recomendação consolidada.

---

### 9️⃣ Gatilho Único: Chatbot Corporativo Web (Chainlit)
- Canal de entrada cravado: aplicação em **Chainlit** (`chatbot/app.py`) na porta 8000.
- Mantém o `session_id` da conversa e despacha as interações via Webhook para o n8n (`POST /webhook/helpdesk-triage`).
- Recebe o JSON consolidado do n8n e renderiza o parecer final com etapas de raciocínio (Chain-of-Thought) para o colaborador.

---

## 🖼️ Diagrama Arquitetural

![[diagrama_arquitetura_9_componentes.svg]]

---

## ⚡ Comandos Rápidos de Inicialização

```bash
# Agente 1 (Triagem - Porta 8001):
uvicorn agent1.app:app --host 0.0.0.0 --port 8001 --reload

# Agente 2 (Remediação - Porta 8002):
uvicorn agent2.app:app --host 0.0.0.0 --port 8002 --reload

# Chatbot Chainlit (Porta 8000):
chainlit run chatbot/app.py -w
```
