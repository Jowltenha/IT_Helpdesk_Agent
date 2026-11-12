# Relatório Técnico - TP4: Orquestração Multi-Agente no n8n, Governança Formal, Skills e Subagentes

**Disciplina:** Engenharia de Prompts e Agentes de IA  
**Aluno:** João Pedro Barboza  
**Projeto:** Sistema de Agentes Inteligentes de Suporte de TI Corporativo (N1 / N2)  
**Data:** Novembro de 2026  
**Status:** Concluído e Validado  

---

## 📌 1. Visão Geral e Objetivos do TP4

O **Trabalho Prático 4 (TP4)** consolida a arquitetura de agentes de IA desacoplados em um pipeline corporativo governado, seguro e orquestrado de ponta a ponta. 

Enquanto os trabalhos anteriores estabeleceram os contratos dos microserviços e o protótipo inicial, o TP4 implementa:
1. **Orquestração Real e Completa no n8n:** Submissão assíncrona, loop de polling determinístico, roteamento condicional inteligente, **AI Agent Node com LLM e Tool** e **Sub-workflow reutilizável**.
2. **Especificação Formal por Agente:** Configuração de regras estritas de permissão (`allow`, `deny`, `ask`) via `settings.json` e implementação de **Hooks automatizados e verificáveis** (`PreToolUse` e `PostToolUse`).
3. **Decomposição em Skills e Subagentes:** Extração de capacidades em arquivos `SKILL.md` padronizados e criação de **Subagentes especializados com isolamento de contexto formalmente justificado**.
4. **Atualização dos Contratos (`CLAUDE.md` e `AGENTS.md`):** Manutenção dos arquivos como fonte única da verdade técnica e mapeamento rigoroso entre requisitos e implementação.

---

## 🌐 2. Orquestração dos Agentes no n8n com Ciclo Assíncrono Completo

O **n8n** atua como o **único orquestrador** do sistema. O Agente 1 e o Agente 2 são microserviços autônomos que operam em portas dedicadas (8001 e 8002) sem acoplamento direto de código ou rede entre si.

```text
[Chatbot Chainlit (Webhook)]
          │ POST /helpdesk-triage-tp4
          ▼
 [HTTP: POST /run (Agente 1)] ──► Retorna 202 + task_id
          │
  [Wait Node (2s)] ◄─────────────┐ (Loop de Polling)
          │                      │
[HTTP: GET /status/{task_id}] ───┘ (Até status: "done")
          │
[AI Agent Node (Supervisor / LLM + Tool)]
          │
 [If: Requer Remediação?]
 ├── SIM (Acessos/VPN) ──► [HTTP: POST /run (Agente 2)] ──► [Wait 2s] ──► [GET /status (Agente 2)]
 │                                                                            │
 └── NÃO (Hardware/Dúvida) ───────────────────────────────────────────────────┼──┐
                                                                              │  │
[Execute Sub-workflow (SLA Calculator & Sanitizer)] ◄─────────────────────────┘  │
          │                                                                      │
          └─────────────────────► [Merge Node] ◄─────────────────────────────────┘
                                       │
                         [Respond to Webhook (Chatbot)]
```

### 2.1 Workflow Principal (`workflows/tp4_main_orchestration_workflow.json`)
O workflow principal implementa a esteira integrada:
1. **Gatilho de Entrada (Nó 1):** `Webhook Trigger` recebe o relato do usuário (`user_prompt`) e o `session_id` originados do Chatbot Corporativo (Chainlit).
2. **Invocação Assíncrona Agente 1 (Nó 2):** Dispara `POST http://localhost:8001/run` enviando `RunRequest`. A API do Agente 1 devolve imediatamente código `202 Accepted` com `task_id`.
3. **Pausa Não-Bloqueante (Nó 3):** Nó `Wait` pausa a execução por 2 segundos para dar tempo à inferência generativa, busca RAG e chamadas de ferramentas.
4. **Polling de Estado Agente 1 (Nó 4):** Consulta `GET http://localhost:8001/status/{task_id}` até que o estado transite para `done`, eliminando timeouts de gateway.
5. **AI Agent Node com LLM e Tool (Nó 5):** Nó de Inteligência Artificial nativo do n8n (`@n8n/n8n-nodes-langchain.agent`) conectado a:
   - **Language Model:** `OpenAI Chat Model` (`gpt-4o-mini`).
   - **Agent Tool:** `Custom Tool - IT Policy Checker` (consulta regras corporativas de segurança).
   - *Responsabilidade:* Analisa criticamente o diagnóstico do Agente 1 e arbitra de forma autônoma se a ação de remediação é segura para execução automática.
6. **Roteamento Condicional (Nó 6):** Nó `If` direciona o fluxo:
   - Incidentes de conta bloqueada no Active Directory ou instabilidade de gateway VPN acionam o ramo do Agente 2.
   - Incidentes de hardware presencial ou consultas informativas seguem direto para cálculo de SLA sem alterar sistemas.
7. **Invocação Assíncrona Agente 2 (Nós 7 a 9):** Repete o ciclo assíncrono para o Agente 2 (`POST http://localhost:8002/run` + Wait 2s + polling em `GET /status/{task_id}`).
8. **Invocação do Sub-workflow (Nó 10):** Nó `Execute Workflow` despacha os dados para o sub-workflow `tp4_subworkflow_sla_calculator`.
9. **Merge Consolidado (Nó 11):** Nó `Merge` funde a triagem N1, as evidências de remediação N2 e os metadados de governança de SLA.
10. **Resposta ao Chatbot (Nó 12):** Devolve ao colaborador a resposta rica formatada.

### 2.2 Sub-workflow Reutilizável (`workflows/tp4_subworkflow_sla_calculator.json`)
Encapsula lógica corporativa isolada e reutilizável:
- **Gatilho Modular:** `Execute Workflow Trigger` permite que o sub-workflow seja invocado pelo workflow principal ou chamado de forma independente em pipelines de auditoria.
- **Lógica de Cálculo de SLA:** Nó `Code` em JavaScript que mapeia a severidade para a matriz formal de tempo de atendimento:
  - *Crítica:* 30 minutos | *Alta:* 120 minutos | *Média:* 480 minutos | *Baixa:* 1440 minutos.
  - Computa a data e hora limite exatas em formato ISO 8601 (`sla_deadline_iso`).
- **Detecção de Criticidade:** Nó `If` verifica se o SLA é `<= 60 minutos` e aciona a flag de alerta imediato (`PAGERDUTY_ALERT_TRIGGERED`).

---

## 🛡️ 3. Especificação Formal de Cada Agente: Permissões e Hooks

### 3.1 Agente 1 (Triagem N1)

#### A) Políticas de Permissão (`agent1/settings.json`)
- **Regras `allow`:** 
  - Execução de testes de API (`python3 agent1/test_agent1_api.py`, `python3 agent1/hooks/test_hook.py`, `pytest`).
  - Leitura de arquivos de código e escrita estrita em arquivos de log (`execution_log.json`, `hooks/hook_audit.log`).
- **Regras `deny`:**
  - Comandos destrutivos de terminal (`rm -rf *`, `git push --force*`, `drop database`).
  - Remoção acidental do banco de sessões relacionais (`rm -rf agent1/agent1_sessions.db`).
  - Chamadas de deleção HTTP (`curl -X DELETE *`).
- **Regras `ask`:**
  - Comandos que alterem o banco de dados diretamente via SQL (`sqlite3 agent1/agent1_sessions.db`).
  - Modificação em arquivos estruturais da API (`models.py`, `app.py`, `runner.py`).

#### B) Hook Automatizado e Verificável: `PreToolUse` (`agent1/hooks/pre_tool_validator.py`)
- **Momento de Execução:** Disparado imediatamente antes de o Agente 1 invocar qualquer ferramenta (`check_system_status`, `lookup_user_account`, `query_troubleshooting_kb`).
- **Comportamento Automatizado:**
  1. Sanitiza argumentos removendo caracteres perigosos de injeção (`;`, `|`, `&`, `$`, `\`).
  2. Valida o formato de e-mail corporativo: exige domínio `@empresa.com`. E-mails externos (`@gmail.com`) ou malformados são bloqueados antes de atingir o Active Directory.
  3. Valida se o serviço consultado faz parte do catálogo de infraestrutura monitorado.
  4. Registra cada decisão no arquivo de auditoria `agent1/hooks/hook_audit.log`.
- **Verificação Automatizada:** Validado através do script `agent1/hooks/test_hook.py` (7 casos de teste cobrindo aprovação, bloqueio e auditoria).

---

### 3.2 Agente 2 (Auto-Remediação N2)

#### A) Políticas de Permissão (`agent2/settings.json`)
- **Regras `allow`:**
  - Execução controlada de testes de remediação (`test_agent2_api.py`, `test_hook.py`).
  - Gravação de trilha de auditoria em `security_audit.log` e `execution_log.json`.
- **Regras `deny`:**
  - Exclusão ou alteração de logs de auditoria (`rm execution_log.json`, `rm security_audit.log`).
  - Comandos de remoção de usuários de sistema (`userdel`).
- **Regras `ask`:**
  - Operações de desbloqueio em lote ou despacho de incidentes para nível executivo.

#### B) Hook Automatizado e Verificável: `PostToolUse` (`agent2/hooks/post_tool_auditor.py`)
- **Momento de Execução:** Disparado imediatamente após a execução de ferramentas de remediação (`unlock_user_account`, `configure_vpn_failover_route`, `dispatch_sla_incident`).
- **Comportamento Automatizado:**
  1. Captura os parâmetros e o resultado retornado pela ferramenta.
  2. Gera um hash criptográfico SHA-256 único e imutável baseado na combinação: `ação + argumentos + resultado + timestamp UTC`.
  3. Injeta no payload retornado o campo `compliance_hash: SEC-XXXX` e a marcação `verified_by_hook: true`.
  4. Persiste a trilha de segurança em `agent2/hooks/security_audit.log` para conformidade com normas SOX e LGPD.
- **Verificação Automatizada:** Validado através do script `agent2/hooks/test_hook.py`.

---

## 🧩 4. Skills Reutilizáveis e Subagentes com Isolamento de Contexto

### 4.1 Skills Reutilizáveis (`SKILL.md`)

| Agente | Arquivo da Skill | Nome da Skill | Finalidade Técnica |
| :---: | :--- | :--- | :--- |
| **Agente 1** | [`agent1/SKILL.md`](agent1/SKILL.md) | `active-directory-diagnostics` | Procedimento Operacional Padrão (SOP) para diagnóstico de bloqueios de credenciais, erros de permissão 403 e validação de grupos no Active Directory. |
| **Agente 2** | [`agent2/SKILL.md`](agent2/SKILL.md) | `sla-incident-dispatch` | Protocolo e matriz corporativa para cálculo de metas de SLA em minutos (30, 120, 480, 1440) e despacho formal ITSM. |

Ambos os arquivos contêm frontmatter YAML válido com `name`, `description`, `version`, `author`, `tags` e `parameters` tipados.

---

### 4.2 Subagentes Projetados e Justificativa Formal de Isolamento

#### Subagente 1: `kb-researcher` (`agent1/subagents/kb_researcher.md`)
- **Contexto:** Subordinado ao Agente 1 (Triagem N1).
- **Modelo:** `ag/claude-sonnet-4-6`.
- **Ferramentas Exclusivas:** `query_troubleshooting_kb`, `check_system_status`.
- **Justificativa Formal de Isolamento de Contexto:**
  > *Artigos procedurais de Base de Conhecimento (SOPs) possuem dezenas de parágrafos com comandos técnicos, variações de sistemas operacionais e notas de rodapé. Carregar esses documentos na janela de contexto principal do Agente 1 causa poluição e saturação da janela de atenção (Context Window Pollution), distraindo o modelo do relato específico do usuário e elevando desnecessariamente o custo de inferência. O subagente `kb-researcher` atua como um pesquisador isolado: recebe a dúvida técnica, consulta a documentação em escopo fechado e devolve ao agente principal apenas o extrato cirúrgico de 3 a 5 linhas acionáveis.*

#### Subagente 2: `sla-compliance-auditor` (`agent2/subagents/sla_auditor.md`)
- **Contexto:** Subordinado ao Agente 2 (Auto-Remediação N2).
- **Modelo:** `ag/claude-sonnet-4-6`.
- **Ferramentas Exclusivas:** `dispatch_sla_incident`.
- **Justificativa Formal de Isolamento de Contexto:**
  > *O Agente 2 opera ações técnicas privilegiadas de modificação de infraestrutura (desbloqueio de contas no Active Directory e provimento de chaves temporárias de VPN). O subagente `sla-compliance-auditor` opera com isolamento de privilégio na camada de governança e cálculo contratual de prazos. Separar esse componente garante que o cálculo de SLA e o registro no ITSM ocorram de forma imutável, sem que estados transitórios de erros de rede ou credenciais interfiram nas regras de conformidade corporativa (SOX / ISO 27001).*

---

## 🤖 5. Uso do Claude Code no Desenvolvimento e Validação

Durante todo o ciclo de desenvolvimento do TP4, o **Claude Code** foi utilizado no terminal integrado como agente de engenharia:
1. **Modelagem de Políticas:** Construção das permissões formais `allow`, `deny` e `ask` no arquivo `settings.json`.
2. **Engenharia de Hooks:** Implementação dos interceptores `pre_tool_validator.py` e `post_tool_auditor.py` com testes unitários de borda.
3. **Consistência de Contratos:** Auditoria contínua entre o código Python (Pydantic v2), as rotas FastAPI e a especificação do `CLAUDE.md` e `AGENTS.md`.
4. **Validação Estrutural:** Verificação de esquemas JSON dos workflows do n8n para garantir compatibilidade com as versões dos nós de LangChain e Core.

---

## 📊 6. Mapeamento Geral de Requisitos e Entregáveis

| Requisito do Projeto | Componente Implementado | Arquivo / Tecnologia | Status |
| :--- | :--- | :--- | :---: |
| **Orquestração Assíncrona no n8n** | Pipeline completo com POST /run + Wait 2s + Polling GET /status | `workflows/tp4_main_orchestration_workflow.json` | ✅ Concluído |
| **Agent Node no n8n** | Nó cognitivo de supervisão conectado a LLM e Tool | Nó `@n8n/n8n-nodes-langchain.agent` no workflow principal | ✅ Concluído |
| **Sub-workflow Reutilizável** | Cálculo corporativo de SLA e prazos contratuais | `workflows/tp4_subworkflow_sla_calculator.json` | ✅ Concluído |
| **Merge e Roteamento** | Roteamento condicional (If) e fusão de dados (Merge) | Nós de controle e merge no n8n | ✅ Concluído |
| **Permissões por Agente** | Regras `allow`, `deny`, `ask` | `agent1/settings.json` e `agent2/settings.json` | ✅ Concluído |
| **Hook PreToolUse** | Sanitização e validação de domínio corporativo | `agent1/hooks/pre_tool_validator.py` | ✅ Concluído |
| **Hook PostToolUse** | Injeção de hash SHA-256 e auditoria de segurança | `agent2/hooks/post_tool_auditor.py` | ✅ Concluído |
| **Skills Reutilizáveis** | Procedimentos operacionais padronizados | `agent1/SKILL.md` e `agent2/SKILL.md` | ✅ Concluído |
| **Subagentes com Isolamento** | Pesquisa de KB e Auditoria de SLA isolados | `agent1/subagents/kb_researcher.md` e `agent2/subagents/sla_auditor.md` | ✅ Concluído |
| **Contratos Atualizados** | Fonte única da verdade técnica por agente | `CLAUDE.md` e `AGENTS.md` em `agent1/` e `agent2/` | ✅ Concluído |
| **Gatilho Oficial** | Chatbot corporativo Web em Chainlit | `chatbot/app.py` via Webhook HTTP | ✅ Concluído |

---

## 🎬 7. Roteiro Sugerido para o Vídeo de Demonstração (Até 5 minutos)

Para gravação do vídeo exigido no Moodle, siga este roteiro planejado minuto a minuto:

| Minuto | Tela a Exibir | O que Falar / Demonstrar |
| :---: | :--- | :--- |
| **00:00 - 01:00** | VS Code mostrando a estrutura do projeto | - Apresentar seu nome e a disciplina.<br>- Mostrar as pastas independentes `agent1/` e `agent2/`.<br>- Destacar a evolução do TP4: `settings.json` com permissões, os hooks em `hooks/`, as skills em `SKILL.md` e os subagentes em `subagents/`. |
| **01:00 - 02:00** | Terminal executando os testes dos Hooks | - Rodar `python3 agent1/hooks/test_hook.py` e mostrar o bloqueio de e-mails inválidos e o log em `hook_audit.log`.<br>- Rodar `python3 agent2/hooks/test_hook.py` e mostrar o hash criptográfico SHA-256 gerado pelo PostToolUse. |
| **02:00 - 03:30** | Interface do n8n (`http://localhost:5678`) | - Mostrar o workflow principal `tp4_main_orchestration_workflow.json`.<br>- Explicar os nós: Webhook, disparo do Agente 1, Wait (2s), polling de status.<br>- Destacar o **AI Agent Node com LLM e Tool** atuando como classificador.<br>- Destacar o nó **Execute Workflow** que chama o **Sub-workflow de SLA** isolado.<br>- Mostrar o nó de Merge unificando tudo. |
| **03:30 - 04:30** | Chatbot Chainlit no Navegador (`http://localhost:8000`) | - Enviar a mensagem: *"Não consigo acessar a folha de pagamento. Erro 403. E-mail maria.souza@empresa.com"*. <br>- Alternar rapidamente para o n8n para mostrar os nós acendendo em verde em tempo real.<br>- Voltar ao Chainlit e mostrar a resposta final com triagem, desbloqueio de conta, SLA de 15 minutos e hash de compliance. |
| **04:30 - 05:00** | Conclusão no VS Code / GitHub | - Ressaltar que os dois agentes operam de forma 100% desacoplada.<br>- O n8n é o único orquestrador e a especificação formal foi integralmente atendida.<br>- Finalizar agradecendo e encerrar. |

---

## 📦 8. Instruções para Submissão no Moodle

1. **Repositório GitHub:**
   - Faça commit e push de todos os arquivos do TP4 para o seu repositório:
     `git add . && git commit -m "feat: implementa entregaveis completos do TP4" && git push origin main`
2. **Relatório em Markdown / PDF:**
   - Envie este arquivo `RELATORIO_TECNICO_TP4.md` (ou exportado para PDF, se preferir).
3. **Link do Vídeo:**
   - Faça o upload do vídeo gravado (no YouTube como Não Listado, Google Drive ou OneDrive) e insira o link no topo do relatório do Moodle.
4. **Arquivo ZIP:**
   - Compacte a pasta do projeto (excluindo `.venv` e `__pycache__`) contendo os agentes, workflows e documentações.
