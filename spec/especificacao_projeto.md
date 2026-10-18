# Especificação do Projeto e Arquitetura do Sistema (Evolução TP2)

## 1. Descrição do Problema e Objetivos do TP2

No ambiente corporativo, a equipe de suporte de TI (Nível 1 / Helpdesk) lida diariamente com chamados não estruturados. Na etapa inicial (TP1), construímos um agente básico que classificava solicitações em JSON estático.

No **TP2**, o projeto evolui para um **Protótipo Funcional de Agente de IA**, cobrindo rigorosamente os 7 entregáveis exigidos na matriz de avaliação:

1. **Gatilho de Entrada (Trigger / n8n):** Recebimento de mensagens em texto livre via Webhook (n8n, Chatbot Web, Telegram, Gmail).
2. **Fonte de Informações (Estruturada e Não Estruturada):**
   - *Estruturada:* APIs e mocks de Status de Infraestrutura, Active Directory (JSON) e banco relacional SQLite (`agent_sessions.db`).
   - *Não Estruturada:* Artigos procedimentos operacionais (SOPs) em texto livre da Base de Conhecimento resgatados via RAG semântico.
3. **Diagrama de Arquitetura dos 9 Componentes:** Mapeamento em camadas numeradas de 1 a 9.
4. **Descrição Textual dos 9 Componentes:** Detalhamento funcional de cada módulo do sistema.
5. **Exemplo de Fluxo de Dados:** Rastreamento passo a passo da entrada do usuário até o resultado final tipado.
6. **Dado Estruturado:** Mapeamento de tabelas SQLite e contratos de APIs.
7. **Demais Itens do TP2:** Tools Python `@function_tool`, raciocínio encadeado (*Prompt Chaining* / *CoT*), memória persistente, RAG, validação Pydantic v2 e benchmark A/B.

---

## 2. Diagrama de Arquitetura dos 9 Componentes

```text
+-----------------------------------------------------------------------------------+
| 1. GATILHO DE ENTRADA (n8n Webhook / Chatbot Web / Telegram / Gmail)             |
|    Recebe a solicitação em texto livre enviada pelo colaborador.                  |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 2. AGENTE ORQUESTRADOR / RUNNER (HelpdeskAgentRunner em Python)                   |
|    Gerencia o ciclo de vida da requisição, acionando memória, RAG e tools.        |
+-----------------------------------------------------------------------------------+
         |                                |                               |
         v                                v                               v
+------------------+             +-------------------+           +------------------+
| 3. MEMÓRIA DB    |             | 7. ENGINE RAG     |           | FERRAMENTAS      |
| (SQLiteSession)  |             | (VectorEmbeddings)|           | (@function_tool) |
| Histórico SQLite |             | Busca Semântica   |           |                  |
+------------------+             +-------------------+           +------------------+
                                          |                               |
                                          v                               v
                                 +-------------------+           +------------------+
                                 | 6. BASE CONHECIM. |           | 4. STATUS INFRA  |
                                 | (Docs SOPs Text)  |           | 5. ACTIVE DIRECT.|
                                 | Não Estruturada   |           | Dado Estruturado |
                                 +-------------------+           +------------------+
         |                                |                               |
         +--------------------------------+-------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 8. MOTOR DE INFERÊNCIA LLM (Claude Sonnet / AsyncOpenAI)                          |
|    Executa raciocínio Chain-of-Thought & Least-to-Most Prompting.                 |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 9. VALIDADOR DE SCHEMA & FORMATADOR DE SAÍDA (Pydantic v2 / HelpdeskResponse)     |
|    Garante tipagem estrita e gera o retorno final salvo em execution_log.json.   |
+-----------------------------------------------------------------------------------+
```

---

## 3. Descrição dos 9 Componentes da Arquitetura

1. **Gatilho de Entrada (n8n Webhook / Chatbot / App Web):** Ponto de contato onde a solicitação do usuário entra no fluxo do agente.
2. **Agente Orquestrador (`HelpdeskAgentRunner`):** Runner Python que gerencia o estado da execução e interage com os subsistemas.
3. **Memória de Sessão SQLite (`SQLiteSession`):** Armazena e recupera o histórico da conversa mantendo a continuidade do atendimento.
4. **Tool Status de Infraestrutura (`check_system_status`):** Consulta a monitoria de VPN, Folha de Pagamento, ERP e E-mail.
5. **Tool Active Directory (`lookup_user_account`):** Consulta perfil de acesso e bloqueio de contas (`account_locked`).
6. **Base de Conhecimento (Docs Não Estruturados):** Conjunto de artigos e SOPs técnicos em linguagem natural.
7. **Engine RAG Semântico (`VectorEmbeddingRAG`):** Pesquisa semântica por TF-IDF e cosseno para recuperar artigos procedimentos.
8. **Motor de Inferência LLM (`Claude Sonnet` via `AsyncOpenAI`):** Agente raciocinador em etapas (Chain-of-Thought).
9. **Validador de Schema Pydantic v2 (`HelpdeskResponse`):** Valida a saída JSON garantindo *type safety* total.
