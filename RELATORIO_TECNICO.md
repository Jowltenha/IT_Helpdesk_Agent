# Relatório Técnico - Evolução do Agente de Helpdesk de TI (TP2)

**Projeto de Bloco:** Agentes Inteligentes  
**Autor / Aluno:** João Pedro Barboza  
**Repositório GitHub:** `IT_Helpdesk_Agent`  
**Data:** Outubro de 2026  

---

## Sumário
1. [Mapeamento Oficial dos 7 Entregáveis do TP2](#1-mapeamento-oficial-dos-7-entregáveis-do-tp2)
2. [Visão Geral e Evolução do Projeto (TP1 ➡️ TP2)](#2-visão-geral-e-evolução-do-projeto-tp1-➡️-tp2)
3. [Entregável 1: Descrição do Problema e Escopo do Agente](#3-entregável-1-descrição-do-problema-e-escopo-do-agente)
4. [Entregável 2: Arquitetura da Solução e Fluxo de Dados (9 Componentes)](#4-entregável-2-arquitetura-da-solução-e-fluxo-de-dados-9-componentes)
5. [Entregável 3: Documentação das Ferramentas Python (@function_tool)](#5-entregável-3-documentação-das-ferramentas-python-function_tool)
6. [Entregável 4: Pipelines de Raciocínio Encadeado, Memória e RAG](#6-entregável-4-pipelines-de-raciocínio-encadeado-memória-e-rag)
7. [Entregável 5: Saídas Tipadas e Validadas com Pydantic v2](#7-entregável-5-saídas-tipadas-e-validadas-com-pydantic-v2)
8. [Entregável 6: Avaliação A/B, Métricas e Matriz de Riscos](#8-entregável-6-avaliação-ab-métricas-e-matriz-de-riscos)
9. [Guia de Execução e Teste Local](#9-guia-de-execução-e-teste-local)
10. [Instruções para Gravação do Vídeo e Submissão](#10-instruções-para-gravação-do-vídeo-e-submissão)

---

## 1. Mapeamento Oficial dos 7 Entregáveis do TP2

Esta seção atende estritamente à matriz de entregáveis solicitada pelo professor para o TP2:

| # | Entregável | Resumo da Implementação no Projeto |
| :-: | :--- | :--- |
| **1** | **Qual Gatilho n8n / Entrada** | Webhook de Chatbot / Aplicativo Web Corporativo / Telegram que dispara o chamado em linguagem natural para o agente. |
| **2** | **Fonte de Informações (Estruturada e Não Estruturada)** | **Estruturada:** APIs de Status de Infraestrutura, Active Directory (JSON/API) e Banco SQLite (`agent_sessions.db`).<br>**Não Estruturada:** Artigos e procedimentos operacionais (SOPs) em texto livre da Base de Conhecimento recuperados via RAG. |
| **3** | **Diagrama de Arquitetura (9 Componentes)** | Diagrama detalhado mapeando explicitamente os 9 componentes do sistema (ver Seção 4.1). |
| **4** | **Descrição Textual da Arquitetura** | Detalhamento funcional dos papéis e responsabilidades dos 9 componentes (ver Seção 4.2). |
| **5** | **Exemplo do Fluxo de Dados** | Rastreamento passo a passo desde a entrada do usuário até o retorno tipado final (ver Seção 4.3). |
| **6** | **Dado Estruturado (DB / API)** | Mapeamento das tabelas SQLite (`session_messages`) e estruturas JSON consultadas/armazenadas (ver Seção 4.4). |
| **7** | **Demais Itens do TP2** | Tools Python `@function_tool`, Prompt Chaining (4 etapas), Memória SQLite, RAG, Pydantic v2 e Avaliação A/B. |

---

## 2. Visão Geral e Evolução do Projeto (TP1 ➡️ TP2)

Na primeira etapa (TP1), o sistema consistia em um protótipo inicial capaz de receber uma string de texto livre e retornar um objeto JSON simples. Embora funcional, o agente era limitado: operava em **single-shot**, sem acesso a fontes externas de dados, sem retenção de memória entre execuções e sem raciocínio estruturado em etapas.

Neste **TP2**, o sistema foi transformado em um **agente de IA genuinamente funcional e autônomo**, que evoluiu nas três frentes exigidas:

1. **Acesso a Dados Externos (Tools):** Integração de ferramentas Python com `@function_tool` para consultar status de infraestrutura, Active Directory e artigos de suporte.
2. **Decomposição e Raciocínio Encadeado (Prompt Chaining & CoT):** Estruturação do raciocínio em múltiplos passos com as técnicas *Least-to-Most Prompting* e *Chain-of-Thought*.
3. **Memória Persistente (SQLiteSession) & RAG Semântico:** Persistência relacional em banco SQLite para histórico de conversas e pipeline RAG baseado em *vector embeddings* para recuperação de artigos procedimentos.

---

## 3. Entregável 1: Descrição do Problema e Escopo do Agente

### 3.1 O Desafio Operacional
No ambiente corporativo, equipes de suporte de TI Nível 1 lidam com centenas de solicitações não estruturadas diariamente via e-mail e chat. A triagem manual acarreta atrasos na identificação de urgências, categorização incorreta de chamados e alocação ineficiente de especialistas.

### 3.2 Escopo da Solução do Agente (TP2)
O agente atua como triador inteligente de Nível 1, capaz de receber solicitações em linguagem natural, consultar de forma autônoma o estado de serviços e contas de usuários, resgatar artigos procedurais via RAG, formatar saídas validadas via Pydantic v2 e decidir sobre a necessidade de escalonamento para N2/N3.

---

## 4. Entregável 2: Arquitetura da Solução e Fluxo de Dados (9 Componentes)

### 4.1 Diagrama de Arquitetura dos 9 Componentes

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

### 4.2 Descrição Textual dos 9 Componentes da Arquitetura

1. **Gatilho de Entrada (Trigger / n8n):** Ponto de entrada do sistema (Webhook n8n, Chatbot Web, Telegram ou Gmail) que captura a mensagem em linguagem natural do colaborador.
2. **Agente Orquestrador (`HelpdeskAgentRunner`):** Componente em Python que gerencia o fluxo de execução, coordena as chamadas à memória, ao RAG e às ferramentas externas.
3. **Memória de Sessão SQLite (`SQLiteSession`):** Banco relacional local (`agent_sessions.db`) que almacena o histórico de conversas agrupado por `session_id`.
4. **Tool de Status de Infraestrutura (`check_system_status`):** Ferramenta Python que consulta a API de monitoria para obter o estado operacional de serviços (VPN, Folha, ERP, E-mail).
5. **Tool de Active Directory (`lookup_user_account`):** Ferramenta Python que consulta a API de gestão de usuários para verificar permissões e o estado de bloqueio da conta (`account_locked`).
6. **Base de Conhecimento (Documentos Não Estruturados):** Repositório de procedimentos operacionais padrão (SOPs e artigos de troubleshooting em texto livre).
7. **Engine RAG Semântico (`VectorEmbeddingRAG`):** Mecanismo de busca semântica que calcula embeddings e similaridade de cosseno para resgatar os artigos procedimentos relevantes.
8. **Motor de Inferência LLM (`Claude Sonnet` via `AsyncOpenAI`):** Modelo de linguagem que processa o prompt enriquecido com contexto e realiza a decomposição Chain-of-Thought.
9. **Validador de Schema Pydantic (`HelpdeskResponse`):** Camada de segurança e tipagem que valida a estrutura JSON final e persiste os logs em `execution_log.json`.

---

### 4.3 Exemplo do Fluxo de Dados Passo a Passo

1. **Entrada do Usuário:** *"Minha conta maria.souza@empresa.com não consegue acessar a folha de pagamento e aparece o erro 'Acesso Negado 403'. Preciso fechar o relatório até 17h."*
2. **Disparo do Gatilho:** O Webhook n8n envia a requisição HTTP POST para o Orquestrador Python.
3. **Consulta de Memória (Componente 3):** O Orquestrador recupera no SQLite as últimas mensagens da sessão `sessao_demonstracao_tp2`.
4. **Execução de Tools Estruturadas (Componentes 4 e 5):**
   - `check_system_status("folha")` ➡️ Retorna status `Operational`.
   - `lookup_user_account("maria.souza@empresa.com")` ➡️ Retorna `account_locked: True`.
5. **Recuperação RAG Não Estruturada (Componentes 6 e 7):**
   - O RAG analisa o texto e resgata o artigo **KB-101** (*Erro 403 / Acesso Negado* - Relevância: 0.92).
6. **Processamento LLM com CoT (Componente 8):** A LLM sintetiza os achados: o serviço está no ar, mas a conta da coordenadora está bloqueada no Active Directory.
7. **Validação Pydantic e Saída (Componente 9):** O resultado é validado pela Pydantic e retornado ao colaborador com recomendação de desbloqueio N2 e severidade Alta.

---

### 4.4 Dado Estruturado (Armazenamento e Consulta)

- **Informações Consultadas em API/DB (Dado Estruturado):**
  - **Monitoria:** `service_name`, `status`, `message`, `last_updated`.
  - **Active Directory:** `email`, `name`, `role`, `groups`, `account_locked`.
- **Informações Armazenadas em Banco SQLite (`agent_sessions.db`):**
  - Tabela `session_messages`: `id`, `session_id`, `role`, `content`, `timestamp`.
  - Logs de Auditoria em `agent/execution_log.json`.

---

## 5. Entregável 3: Documentação das Ferramentas Python (@function_tool)

O agente dispõe de 3 ferramentas desenvolvidas em Python (`agent/tools.py`), utilizando o decorador `@function_tool` e *type annotations* nativas:

| Nome da Tool | Parâmetros | Tipo de Retorno | Finalidade / Descrição |
| :--- | :--- | :--- | :--- |
| `check_system_status` | `service_name: str` | `str` (JSON) | Consulta a monitoria de infraestrutura para obter o status operacional de serviços. |
| `lookup_user_account` | `user_email: str` | `str` (JSON) | Consulta o Active Directory para verificar permissões e estado de bloqueio da conta (`account_locked`). |
| `query_troubleshooting_kb` | `query: str` | `str` (JSON) | Pesquisa na base de dados de suporte por artigos de solução e procedimentos recomendados. |

---

## 6. Entregável 4: Pipelines de Raciocínio Encadeado, Memória e RAG

### 6.1 Raciocínio Encadeado (Prompt Chaining & Least-to-Most)
Implementado em `prompts/prompt_chaining.py`, o fluxo divide chamados complexos em 4 fases: Decomposição ➡️ Verificação Externa ➡️ Síntese CoT ➡️ Formatação Validada.

### 6.2 Memória Persistente de Sessão (SQLiteSession)
Gerenciada em `agent/memory.py`, a classe `SQLiteSession` persiste o histórico de mensagens no banco relacional `agent_sessions.db`.

### 6.3 Pipeline RAG Semântico (Vector Embedding)
Desenvolvido em `agent/rag.py`, a classe `VectorEmbeddingRAG` gera representações vetoriais dos artigos da Base de Conhecimento e calcula a similaridade de cosseno para resgatar os procedimentos operacionais mais relevantes.

---

## 7. Entregável 5: Saídas Tipadas e Validadas com Pydantic v2

A classe `HelpdeskResponse` (`agent/models.py`) define o contrato estrito de saída do agente:

```python
class HelpdeskResponse(BaseModel):
    ticket_summary: str = Field(description="Resumo claro do problema em até 10 palavras.")
    category: str = Field(description="Hardware, Software, Redes/VPN, Acessos/Senhas ou Outros.")
    severity: str = Field(description="Baixa, Média, Alta ou Crítica.")
    recommended_action: str = Field(description="Passos ou recomendações imediatas.")
    requires_human_escalation: bool = Field(description="True se exigir N2/N3 ou presencial.")
    reasoning_steps: List[str] = Field(description="Etapas do raciocínio Chain-of-Thought.")
    tools_invoked: List[str] = Field(description="Ferramentas Python consultadas.")
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0)
```

---

## 8. Entregável 6: Avaliação A/B, Métricas e Matriz de Riscos

### 8.1 Comparação A/B de Prompts (Benchmark Quantitativo)
A avaliação automatizada executada via `evaluation/evaluate.py` comprovou o salto de desempenho:

| Métrica | Variante A (Baseline) | Variante B (Refinada TP2) | Ganho (%) |
| :--- | :---: | :---: | :---: |
| **SCORE MÉDIO FINAL** | **45.0 / 100** | **100.0 / 100** | **+122.2%** |

---

## 9. Guia de Execução e Teste Local

```bash
# 1. Ativar o ambiente virtual
source .venv/bin/activate

# 2. Executar o Agente Principal (TP2)
python agent/main.py

# 3. Executar o Pipeline de Prompt Chaining
python prompts/prompt_chaining.py

# 4. Executar o Benchmark de Avaliação A/B
python evaluation/evaluate.py
```

---

## 10. Instruções para Gravação do Vídeo e Submissão

### 🎥 Roteiro Recomendado para o Vídeo de 5 Minutos:
1. **0:00 - 0:45 (Introdução):** Apresente-se (João Pedro Barboza), mencione o TP2 e apresente os 9 componentes da arquitetura.
2. **0:45 - 2:00 (Demonstração do Agente e Tools):** Execute `python agent/main.py` e mostre o agente invocando as ferramentas e consultando o Active Directory.
3. **2:00 - 3:00 (Memória SQLite & RAG):** Mostre o **RUN 2** e explique o histórico mantido no banco SQLite e a busca no artigo RAG KB-101.
4. **3:00 - 4:00 (Prompt Chaining & Avaliação A/B):** Mostre os scripts de chaining e o resultado do benchmark (100% de acerto).
5. **4:00 - 5:00 (Conclusão):** Conclua destacando a validação Pydantic v2 e encerre a gravação.
