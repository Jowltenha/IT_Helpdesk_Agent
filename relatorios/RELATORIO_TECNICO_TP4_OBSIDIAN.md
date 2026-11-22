---
title: "Relatório Técnico TP4: Orquestração Multi-Agente n8n, Governança, Skills e Subagentes"
date: 2026-11-12
author: "João Pedro Barboza"
project: "IT Helpdesk Agent"
stage: "TP4"
status: "Concluído"
tags:
  - tp4
  - n8n
  - agents-sdk
  - subagents
  - skills
  - hooks
  - governance
  - obsidian
aliases:
  - "Relatório Técnico TP4"
  - "TP4 Orquestração e Governança"
---

> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# 📋 Relatório Técnico TP4: Orquestração no n8n, Governança Formal, Skills e Subagentes

> [!ABSTRACT] Resumo do Entregável
> Este relatório técnico consolida os avanços implementados no **TP4**: orquestração assíncrona completa no n8n com **AI Agent Node**, **Sub-workflow modular**, governança formal com regras `allow`/`deny`/`ask` em `settings.json`, hooks verificáveis `PreToolUse` e `PostToolUse`, skills padronizadas e subagentes com isolamento de contexto formalmente justificado.

---

## 🧭 Sumário de Navegação Rápida

- [[#1. Orquestração Multi-Agente no n8n (Ciclo Completo Assíncrono)|1. Orquestração no n8n]]
  - [[#1.1 Workflow Principal com AI Agent Node|1.1 Workflow Principal]]
  - [[#1.2 Sub-workflow Reutilizável de SLA|1.2 Sub-workflow de SLA]]
- [[#2. Governança Formal: Permissões e Hooks por Agente|2. Governança e Hooks]]
  - [[#2.1 Agente 1: Settings e Hook PreToolUse|2.1 Agente 1 (Triagem)]]
  - [[#2.2 Agente 2: Settings e Hook PostToolUse|2.2 Agente 2 (Remediação)]]
- [[#3. Skills Reutilizáveis e Subagentes com Isolamento de Contexto|3. Skills e Subagentes]]
  - [[#3.1 Skills Padronizadas (SKILL.md)|3.1 Skills Reutilizáveis]]
  - [[#3.2 Subagentes com Isolamento Justificado|3.2 Subagentes Especialistas]]
- [[#4. Atualização dos Contratos (CLAUDE.md e AGENTS.md)|4. Contratos de Desenvolvimento]]
- [[#5. Mapeamento Completo de Requisitos|5. Tabela de Mapeamento]]
- [[#6. Roteiro para Gravação do Vídeo de Demonstração (5 min)|6. Roteiro do Vídeo]]

---

## 1. Orquestração Multi-Agente no n8n (Ciclo Completo Assíncrono)

> [!INFO] Princípio Arquitetural
> O **n8n** é o orquestrador soberano da esteira. O Agente 1 (Triagem N1 na porta 8001) e o Agente 2 (Auto-Remediação N2 na porta 8002) **não se comunicam diretamente** e desconhecem a infraestrutura um do outro.

![[diagrama_arquitetura_9_componentes.svg]]

### 1.1 Workflow Principal com AI Agent Node
Arquivo: `workflows/tp4_main_orchestration_workflow.json`

- **Webhook Trigger:** Ponto único de entrada conectado ao Chatbot Corporativo Web (Chainlit via `POST /webhook/helpdesk-triage-tp4`).
- **Disparo Assíncrono Agente 1:** Dispara `POST http://localhost:8001/run` e obtém `202 Accepted` acompanhado de um `task_id` imediato.
- **Polling Não-Bloqueante:** Loop com nó de espera (`Wait Node` por 2 segundos) consultando `GET http://localhost:8001/status/{task_id}` até transição para `done`.
- **AI Agent Node com LLM e Tool:**
  - Nó `@n8n/n8n-nodes-langchain.agent` integrado ao modelo `OpenAI Chat Model` (`gpt-4o-mini`) e à ferramenta `Custom Tool - IT Policy Checker`.
  - Atua como o árbitro cognitivo do pipeline: avalia se a recomendação de remediação é segura para execução autônoma.
- **Roteamento Condicional (`If Node`):**
  - Incidentes de Active Directory ou instabilidade de VPN disparam o Agente 2.
  - Incidentes de hardware presencial seguem diretamente para cálculo de SLA sem alteração de sistemas.
- **Invocação do Agente 2:** `POST http://localhost:8002/run` + loop de polling com `Wait Node`.
- **Invocação do Sub-workflow:** Nó `Execute Workflow` despachando dados para o calculador modular de SLA.
- **Nó Merge & Resposta:** Unifica os três fluxos de dados e responde ao Chatbot.

### 1.2 Sub-workflow Reutilizável de SLA
Arquivo: `workflows/tp4_subworkflow_sla_calculator.json`

- **Gatilho Modular:** `Execute Workflow Trigger` permitindo execução em lote ou invocação isolada.
- **Cálculo da Matriz de SLA:**
  - *Crítica:* 30 min | *Alta:* 120 min | *Média:* 480 min | *Baixa:* 1440 min.
  - Cálculo de deadline futuro no padrão ISO 8601 (`sla_deadline_iso`).
- **Detecção de Criticidade:** Flag automática de alerta (`PAGERDUTY_ALERT_TRIGGERED`) quando o tempo limite for `<= 60 minutos`.

---

## 2. Governança Formal: Permissões e Hooks por Agente

### 2.1 Agente 1: Settings e Hook PreToolUse
- **Arquivo de Permissões:** `agent1/settings.json`
  - `allow`: Testes de API, execução do hook e escrita em logs.
  - `deny`: Comandos destrutivos (`rm -rf`, `git push --force`) e deleção de sessões.
  - `ask`: Modificações em schemas Pydantic e queries SQL manuais no SQLite.
- **Hook `PreToolUse` (`agent1/hooks/pre_tool_validator.py`):**
  - Intercepta chamadas a ferramentas antes da execução física.
  - Valida se o e-mail possui domínio corporativo `@empresa.com`.
  - Bloqueia tentativas de injeção de comandos (`;`, `|`, `&`, `$`).
  - Persiste a trilha de auditoria em `agent1/hooks/hook_audit.log`.

### 2.2 Agente 2: Settings e Hook PostToolUse
- **Arquivo de Permissões:** `agent2/settings.json`
  - `allow`: Invocação de remediação controlada e leitura/escrita em logs.
  - `deny`: Exclusão de trilhas de auditoria (`security_audit.log`, `execution_log.json`).
  - `ask`: Desbloqueios em massa ou escalonamento executivo.
- **Hook `PostToolUse` (`agent2/hooks/post_tool_auditor.py`):**
  - Intercepta retornos de ferramentas de remediação.
  - Computa hash criptográfico SHA-256 (`compliance_hash: SEC-XXXX`).
  - Injeta garantias de integridade para compliance SOX e LGPD em `agent2/hooks/security_audit.log`.

---

## 3. Skills Reutilizáveis e Subagentes com Isolamento de Contexto

### 3.1 Skills Padronizadas (SKILL.md)
1. **`agent1/SKILL.md` (`active-directory-diagnostics`):**
   - Procedimento Operacional Padrão para diagnóstico de bloqueios de contas corporativas, análise de Erro 403 e validação de grupos de acesso.
2. **`agent2/SKILL.md` (`sla-incident-dispatch`):**
   - Protocolo formal de cálculo de prazos de atendimento por severidade e despacho de incidentes no sistema ITSM corporativo.

### 3.2 Subagentes com Isolamento Justificado

> [!TIP] Subagente 1: `kb-researcher` (`agent1/subagents/kb_researcher.md`)
> **Modelo:** `ag/claude-sonnet-4-6` | **Tools:** `query_troubleshooting_kb`, `check_system_status`
> **Justificativa de Isolamento:** Manuais de procedimentos técnicos (SOPs) possuem múltiplos parágrafos de comandos e instruções. Injetar a íntegra desses manuais na janela de contexto principal do Agente 1 causa poluição e distração do modelo (Context Window Pollution). O subagente pesquisa em escopo fechado e devolve apenas o resumo cirúrgico acionável.

> [!TIP] Subagente 2: `sla-compliance-auditor` (`agent2/subagents/sla_auditor.md`)
> **Modelo:** `ag/claude-sonnet-4-6` | **Tools:** `dispatch_sla_incident`
> **Justificativa de Isolamento:** O Agente 2 possui ferramentas de alteração ativa de infraestrutura (desbloqueio de AD e chaveamento de VPN). O subagente de auditoria opera de forma isolada na camada de governança e prazos, garantindo conformidade imutável perante auditorias de segurança sem interferência do estado operacional de scripts de rede.

---

## 4. Atualização dos Contratos (CLAUDE.md e AGENTS.md)

Cada agente agora possui contratos atualizados refletindo as capacidades do TP4:
- `agent1/CLAUDE.md` e `agent1/AGENTS.md`: Mapeamento de permissões, hooks, skills e subagentes da triagem N1.
- `agent2/CLAUDE.md` e `agent2/AGENTS.md`: Mapeamento das regras de auto-remediação, governança de SLA e hooks pós-execução.

---

## 5. Mapeamento Completo de Requisitos

| Requisito do TP4 | Implementação no Projeto | Status |
| :--- | :--- | :---: |
| **Workflow n8n com Invocação Assíncrona e Polling** | `workflows/tp4_main_orchestration_workflow.json` | ✅ Concluído |
| **Agent Node com LLM e Tool no n8n** | Nó LangChain com OpenAI Chat Model e IT Policy Checker | ✅ Concluído |
| **Sub-workflow Reutilizável no n8n** | `workflows/tp4_subworkflow_sla_calculator.json` | ✅ Concluído |
| **Roteamento e Merge de Dados** | Nós If e Merge conectando triagem e remediação | ✅ Concluído |
| **Settings com Allow, Deny, Ask** | `agent1/settings.json` e `agent2/settings.json` | ✅ Concluído |
| **Hook PreToolUse Automatizado** | `agent1/hooks/pre_tool_validator.py` | ✅ Concluído |
| **Hook PostToolUse Automatizado** | `agent2/hooks/post_tool_auditor.py` com hash SHA-256 | ✅ Concluído |
| **Skills Reutilizáveis (SKILL.md)** | `agent1/SKILL.md` e `agent2/SKILL.md` com YAML Frontmatter | ✅ Concluído |
| **Subagentes com Isolamento Justificado** | `kb_researcher.md` e `sla_auditor.md` | ✅ Concluído |
| **Contratos Atualizados** | `CLAUDE.md` e `AGENTS.md` em ambos os agentes | ✅ Concluído |

---

## 6. Roteiro para Gravação do Vídeo de Demonstração (5 min)

> [!SUCCESS] Estrutura do Vídeo (Moodle)
> - **Minuto 1:** Explicar a arquitetura dos dois agentes desacoplados no VS Code.
> - **Minuto 2:** Rodar os testes automatizados dos Hooks (`agent1/hooks/test_hook.py` e `agent2/hooks/test_hook.py`) mostrando os logs de auditoria e hashes gerados.
> - **Minuto 3:** Exibir o n8n com o **AI Agent Node**, o nó **Execute Workflow** e o **Sub-workflow de SLA**.
> - **Minuto 4:** Demonstrar uma chamada real através do Chatbot Chainlit no navegador e mostrar os nós acendendo em verde no n8n.
> - **Minuto 5:** Fechar destacando o cumprimento das especificações formais do TP4.
