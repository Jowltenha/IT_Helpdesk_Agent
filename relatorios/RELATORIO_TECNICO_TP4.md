> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# Relatório Técnico - TP4: Orquestração Multi-Agente Assíncrona no n8n, Governança, Skills e Subagentes

**Disciplina:** Engenharia de Prompts e Agentes de IA
**Aluno:** João Pedro Barboza
**Projeto:** Sistema de Agentes Inteligentes de Suporte de TI Corporativo (N1 / N2)
**Repositório:** https://github.com/Jowltenha/IT_Helpdesk_Agent
**Data:** Novembro de 2026 (versão revisada após a correção do professor)

---

## 0. Correções feitas após o feedback do professor

O feedback da primeira entrega foi:

> *"Faltou a parte assíncrona do N8N, de não esperar os agentes terminarem. Além disso, faltaram o vídeo e o link do GitHub."*
>
> Pendências: vídeo de até 5 min; link do GitHub; **laço de polling nos dois agentes, voltando ao Wait enquanto o status for `pending`, e Merge recebendo as respostas dos dois agentes.**

| Pendência apontada | O que estava errado | O que foi corrigido |
| :--- | :--- | :--- |
| **n8n assíncrono (não esperar os agentes)** | O Webhook usava `Respond to Webhook` só no **final** do fluxo, então o chatbot ficava esperando os dois agentes terminarem. | Agora o n8n responde **`202 Accepted` + `ticket_id` imediatamente**, logo após registrar o chamado. Os agentes rodam **em segundo plano** e o progresso fica salvo na Data Table `helpdesk_tickets`. Um segundo webhook (`GET /webhook/helpdesk-status?ticket_id=...`) permite consultar o andamento. |
| **Laço de polling nos dois agentes** | Havia só **um** Wait de 2 s e **uma** consulta ao `/status`, sem laço. | Cada agente tem o ciclo `Wait 3s → GET /status → Switch`. A saída **`pendente_volta_ao_wait`** volta para o Wait **enquanto `status == "pending"`** (até 40 tentativas ≈ 2 min). `done` segue o fluxo. `error` ou timeout vai para o tratamento de falha. |
| **Merge recebendo as respostas dos dois agentes** | O Merge tinha só **uma** entrada conectada. | O nó **`Merge: Respostas dos 2 Agentes`** recebe na **entrada 1** a resposta do Agente 1 e na **entrada 2** a resposta do Agente 2 (ou o aviso "Agente 2 não necessário", quando o Supervisor decide que não há remediação). |
| **Link do GitHub** | Não constava na entrega. | Adicionado no topo deste e de **todos** os relatórios, e registrado como regra no `CLAUDE.md` do projeto. |
| **Vídeo** | Não foi enviado. | Roteiro de 5 minutos pronto (seção 8). A gravação precisa ser feita pelo aluno. |

**Outras correções encontradas durante a revisão:**
- **URLs dos agentes:** o n8n roda em Docker, onde `localhost` aponta para o próprio container. As URLs passaram de `http://localhost:800X` para `http://local:800X` (host da máquina).
- **ID real do sub-workflow:** o nó Execute Workflow apontava para um ID fictício (`subworkflow-sla-calculator`). Agora usa o ID real (`BPDzhhNbkyZ4VDoI`).
- **Modelo do AI Agent:** usava `gpt-4o-mini` sem credencial. Agora aponta para o mesmo proxy dos agentes (`http://local:20128/v1`, modelo `ag/claude-sonnet-4-6`).
- **Bug no Agente 1 (`agent1/runner.py`):** o OpenAI Agents SDK lia a barra em `ag/claude-sonnet-4-6` como prefixo de provedor e falhava com `Unknown prefix: ag`. O modelo agora é envolvido em `OpenAIChatCompletionsModel`, e o cliente do proxy é usado diretamente.
- **Saída estruturada do Agente 1:** o modelo do proxy às vezes devolve o JSON cercado de texto e de um bloco ` ```json `, e o SDK falhava com `Invalid JSON when parsing model output`. Foi criado o `MarkdownTolerantOutputSchema`, que extrai só o objeto JSON antes da validação. A validação Pydantic do `HelpdeskResponse` continua estrita.
- **Chatbot (`chatbot/app.py`):** agora aceita o `202`, mostra "chamado recebido" na hora e consulta o status a cada 3 s até o resultado ficar pronto. Também foi corrigido o uso da API do Chainlit (`msg.content = ...; await msg.update()`). Botões no chat substituem os comandos de terminal:
  - **Verificar serviços:** agentes, workflow publicado e proxy do LLM.
  - **Testar hooks de segurança:** casos de bloqueio do PreToolUse e hash do PostToolUse.
  - **Consultar status no n8n:** consulta o webhook de status do chamado.
  - **Ver trilha de auditoria dos hooks:** eventos reais gravados pelos hooks para aquele chamado.
- **SLA:** o roteiro antigo citava "SLA de 15 minutos", o que não corresponde à matriz real. Para severidade **Alta** o SLA é **120 minutos**.

---

## 1. Visão geral do TP4 (em linguagem simples)

O sistema recebe um chamado de TI escrito pelo colaborador num chat e resolve o que for possível automaticamente:

1. **Agente 1 – Triagem N1** (Python, porta 8001). Lê o chamado, consulta ferramentas (status de sistemas, Active Directory, base de conhecimento com RAG) e devolve um laudo: categoria, severidade, ação recomendada e se precisa de humano.
2. **Agente 2 – Remediação N2** (Python, porta 8002). Recebe o laudo e executa a correção: desbloqueia a conta, cria rota de VPN de contingência ou abre incidente com SLA.
3. **n8n – Orquestrador.** É o único componente que conversa com os dois agentes. Os agentes **não se conhecem**.
4. **Agente Supervisor dentro do n8n** (AI Agent node). Lê o laudo do Agente 1, consulta a ferramenta `query_support_policy` e decide se o Agente 2 deve agir.
5. **Sub-workflow de SLA.** Fluxo n8n separado e reutilizável que calcula prazo, equipe e urgência.
6. **Chatbot Chainlit.** É a porta de entrada (gatilho único do pipeline).

Além da orquestração, o TP4 pedia **governança formal por agente** (`settings.json` com `allow`/`deny`/`ask`), **hooks verificáveis** (`PreToolUse` / `PostToolUse`), **skills** (`SKILL.md`) e **subagentes com isolamento de contexto**.

---

## 2. Orquestração assíncrona no n8n

### 2.1 Por que assíncrono?

Uma triagem com LLM e ferramentas leva de 10 s a 1 min. Se o webhook esperasse tudo terminar, o chatbot ficaria travado e a requisição HTTP poderia estourar o tempo limite. A solução tem três partes:

- **n8n ↔ chatbot:** o n8n responde **na hora** (`202` + `ticket_id`) e o chatbot consulta o status depois.
- **n8n ↔ agentes:** os agentes também são assíncronos (`POST /run` devolve `202` + `task_id`), e o n8n faz **polling** em `GET /status/{task_id}` até ficar `done`.
- **Estado compartilhado:** a Data Table `helpdesk_tickets` do n8n guarda `status` (`processing` / `done` / `error`), a etapa (`received` → `triage_done` → `completed`) e o resultado final em JSON.

### 2.2 Diagrama do fluxo

```text
 Chatbot ──POST /webhook/helpdesk-triage-tp4──► [Webhook]
                                                   │
                                        [Normalizar Chamado]  (gera ticket_id)
                                                   │
                                   [Registrar Chamado (processing)]  → Data Table
                                                   │
 Chatbot ◄──── 202 {ticket_id, status_endpoint} ── [Responder 202 Imediato]   ◄── o chatbot JÁ foi liberado aqui
                                                   │
                         ───────────── daqui pra baixo roda em SEGUNDO PLANO ─────────────
                                                   │
                                  [Disparar Agente 1 (POST :8001/run)] → 202 + task_id
                                                   │
                         ┌──────────► [Aguardar Agente 1 (3s)]
                         │                         │
                         │            [Consultar Status Agente 1 (GET /status)]
                         │                         │
                         │               [Switch: Agente 1 Terminou?]
                         └── pendente ─────────────┤
                                                   ├── erro/timeout ──► [Preparar Erro] → [Salvar Falha (error)]
                                                done
                                                   │
                               [Atualizar Etapa: triage_done] → Data Table
                                     │                                     │
                     [Agente Supervisor (AI Agent)]              [Resposta do Agente 1] ───────┐
                      LLM + Tool query_support_policy                                          │
                                     │                                                         │
                       [If: Precisa de Remediação?]                                            │
                  sim ───────────────┴────────────── não                                       │
                   │                                  │                                        │
 [Disparar Agente 2 (POST :8002/run)]       [Agente 2 Não Necessário] ───────┐                 │
                   │                                                         │                 │
        ┌──► [Aguardar Agente 2 (3s)]                                        │                 │
        │          │                                                         │                 │
        │  [Consultar Status Agente 2]                                       │                 │
        │          │                                                         ▼                 ▼
        │  [Switch: Agente 2 Terminou?]                               ┌──────────────────────────────┐
        └─ pendente┤                                                  │ Merge: Respostas dos 2       │
                   ├─ erro/timeout ──► [Salvar Falha]                 │ Agentes (entrada 1 = Ag. 1,  │
                 done ──► [Resposta do Agente 2] ───────────────────► │ entrada 2 = Ag. 2)           │
                                                                      └──────────────┬───────────────┘
                                                                                     │
                                                          [Preparar Dados para SLA] → [Executar Sub-workflow de SLA]
                                                                                     │
                                                          [Consolidar Resultado Final] → [Salvar Resultado (done)]

 Chatbot ──GET /webhook/helpdesk-status?ticket_id=...──► [Webhook Status] → [Buscar na Data Table] → [Responder Status]
```

### 2.3 Nós do workflow principal (`workflows/tp4_main_orchestration_workflow.json`)

| # | Nó | Tipo n8n | O que faz |
| :-: | :--- | :--- | :--- |
| 1 | Webhook Chatbot (Novo Chamado) | Webhook (POST `helpdesk-triage-tp4`) | Recebe `user_prompt` e `session_id` do chatbot. |
| 2 | Normalizar Chamado | Set | Gera `ticket_id` (`TCK-AAAAMMDD-HHMMSS-<exec>`) e extrai o e-mail do texto. |
| 3 | Registrar Chamado (processing) | Data Table (insert) | Cria a linha do ticket com `status=processing`. |
| 4 | **Responder 202 Imediato ao Chatbot** | Respond to Webhook (202) | **Libera o chatbot na hora**, sem esperar os agentes. |
| 5 | Disparar Agente 1 (POST /run) | HTTP Request | Inicia a triagem e recebe `task_id`. |
| 6–8 | Aguardar 3s → Consultar Status → **Switch "Agente 1 Terminou?"** | Wait + HTTP + Switch | **Laço de polling:** `pending` volta ao Wait, `done` segue, `error` ou mais de 40 tentativas vai para a falha. |
| 9 | Atualizar Etapa: Triagem Concluída | Data Table (update) | Marca `stage=triage_done` (o chatbot mostra o progresso). |
| 10 | **Agente Supervisor (n8n)** | AI Agent + LLM + Tool + Output Parser | Terceiro agente: decide `should_remediate` e `target_action` consultando `query_support_policy`. Regras, nesta ordem: (1) se o laudo exige escalonamento humano, aciona o Agente 2 com `DISPATCH_INCIDENT` para abrir incidente ITSM para o N2; (2) se a política permite remediação automática, aciona com `UNLOCK_ACCOUNT` ou `VPN_FAILOVER`; (3) caso contrário, não aciona. |
| 11 | Precisa de Remediação (Agente 2)? | If | Roteia para o Agente 2 ou para "não necessário". |
| 12 | Disparar Agente 2 (POST /run) | HTTP Request | Envia o laudo do Agente 1 e a ação escolhida pelo Supervisor. |
| 13–15 | Aguardar 3s → Consultar Status → **Switch "Agente 2 Terminou?"** | Wait + HTTP + Switch | **Mesmo laço de polling** para o Agente 2. |
| 16 | Resposta do Agente 1 / Resposta do Agente 2 / Agente 2 Não Necessário | Set | Padroniza as respostas antes do Merge. |
| 17 | **Merge: Respostas dos 2 Agentes** | Merge (combine by position, 2 entradas) | Junta a resposta do Agente 1 com a do Agente 2. |
| 18 | Executar Sub-workflow de SLA | Execute Workflow | Chama o sub-workflow e espera o retorno do SLA. |
| 19 | Consolidar Resultado Final → Salvar Resultado (done) | Code + Data Table | Monta o JSON final e grava `status=done`. |
| 20 | Preparar Mensagem de Erro → Salvar Falha (error) | Set + Data Table | Qualquer falha (agente fora do ar, erro ou timeout) vira `status=error` com a mensagem. |
| 21 | Webhook Consulta de Status → Buscar → Responder | Webhook GET + Data Table + Respond | Endpoint que o chatbot consulta: devolve `processing`, `done` (com resultado) ou `error`. |

### 2.4 Sub-workflow reutilizável (`workflows/tp4_subworkflow_sla_calculator.json`)

- **Gatilho:** `Execute Workflow Trigger`. Pode ser chamado por qualquer outro workflow.
- **Calcular SLA e Equipe (Code):** aplica a matriz de SLA (Crítica 30 min, Alta 120 min, Média 480 min, Baixa 1440 min), define a equipe responsável (ex.: Acessos/Senhas → *N2 Acessos e Identidade*) e calcula o `sla_deadline_iso`.
- **If "SLA Crítico (até 60 min)?":** marca `CRITICAL_URGENT` (alerta PagerDuty) ou `NORMAL_FLOW`.

### 2.5 Como foi validado

- **Teste sem agentes ligados:** o webhook respondeu 202. O `POST /run` falhou com `ECONNREFUSED`, a falha foi gravada como `status=error` na Data Table e o webhook de status devolveu esse erro. Isso mostra que o chatbot **não fica travado** mesmo com falha.
- **Teste do caminho completo com dados simulados (pin data):** o fluxo passou pelo Agente 1 (`done`), pelo Supervisor, pelo Agente 2 (`done`), pelo **Merge com as 2 entradas**, pelo sub-workflow de SLA (Alta → 120 min, *N2 Acessos e Identidade*) e terminou gravando `status=done` com o resultado consolidado.
- **Teste com os agentes reais:** os agentes subiram e responderam `202` + `task_id`. O polling recebeu o status real, e o bug `Unknown prefix: ag` foi descoberto e corrigido. A execução completa com LLM depende de uma chave válida do proxy 9Router (ver seção 9).

---

## 3. Especificação formal de cada agente: permissões e hooks

### 3.1 Agente 1 (Triagem N1)

**Permissões (`agent1/settings.json`):**
- **allow:** rodar os testes (`test_agent1_api.py`, `hooks/test_hook.py`, `pytest`), ler o código e escrever apenas nos logs (`execution_log.json`, `hook_audit.log`).
- **deny:** comandos destrutivos (`rm -rf`, `git push --force`, `drop database`), apagar `agent1_sessions.db`, `curl -X DELETE`.
- **ask:** alterar `models.py`, `app.py` ou `runner.py`, e mexer no banco SQLite via SQL.

**Hook `PreToolUse` (`agent1/hooks/pre_tool_validator.py`):** roda **antes** de cada ferramenta do Agente 1 e:
1. remove caracteres de injeção (`;`, `|`, `&`, `$`, `\`);
2. só aceita e-mails `@empresa.com` (por exemplo, bloqueia `@gmail.com`);
3. valida se o serviço consultado existe no catálogo;
4. registra cada decisão em `agent1/hooks/hook_audit.log`.

Como verificar: `PYTHONPATH=. python3 agent1/hooks/test_hook.py`

### 3.2 Agente 2 (Remediação N2)

**Permissões (`agent2/settings.json`):**
- **allow:** testes e escrita nas trilhas de auditoria.
- **deny:** apagar ou alterar logs de auditoria, e `userdel`.
- **ask:** desbloqueios em lote e escalonamento executivo.

**Hook `PostToolUse` (`agent2/hooks/post_tool_auditor.py`):** roda **depois** de cada ação de remediação. Ele gera um hash SHA-256 a partir de ação, argumentos, resultado e timestamp, injeta `compliance_hash` e `verified_by_hook: true` no retorno e grava a trilha em `agent2/hooks/security_audit.log` (conformidade SOX/LGPD).

Como verificar: `PYTHONPATH=. python3 agent2/hooks/test_hook.py`

---

## 4. Skills reutilizáveis e subagentes

| Agente | Skill | Para que serve |
| :-: | :--- | :--- |
| Agente 1 | `agent1/SKILL.md` – `active-directory-diagnostics` | Passo a passo para diagnosticar conta bloqueada, erro 403 e grupos do AD. |
| Agente 2 | `agent2/SKILL.md` – `sla-incident-dispatch` | Matriz de SLA (30/120/480/1440 min) e protocolo de abertura de incidente ITSM. |

| Subagente | Dono | Por que é isolado |
| :--- | :--- | :--- |
| `kb-researcher` (`agent1/subagents/kb_researcher.md`) | Agente 1 | Os artigos da base de conhecimento são longos. O subagente lê tudo num contexto separado e devolve só 3 a 5 linhas úteis, sem poluir a janela de contexto do Agente 1. |
| `sla-compliance-auditor` (`agent2/subagents/sla_auditor.md`) | Agente 2 | Separa o cálculo de SLA e o registro ITSM (governança) das ações privilegiadas de infraestrutura, para que um erro técnico não contamine o registro de conformidade. |

---

## 5. Uso do Claude Code no desenvolvimento

O Claude Code foi usado como agente de engenharia em várias frentes:
- modelagem de `settings.json` e implementação dos hooks;
- conferência de consistência entre o código (Pydantic/FastAPI) e os contratos `CLAUDE.md` e `AGENTS.md`;
- nesta revisão, a construção do workflow assíncrono **direto no n8n via MCP**: criação da Data Table, do sub-workflow e do workflow principal, testes de execução e exportação dos JSON para o repositório.

---

## 6. Mapa de requisitos

| Requisito | Onde está | Status |
| :--- | :--- | :-: |
| n8n assíncrono (resposta imediata, sem esperar os agentes) | Nó `Responder 202 Imediato ao Chatbot` + Data Table + webhook `helpdesk-status` | ✅ |
| Laço de polling nos 2 agentes (volta ao Wait enquanto `pending`) | Switches `Agente 1 Terminou?` / `Agente 2 Terminou?` | ✅ |
| Merge recebendo as respostas dos 2 agentes | Nó `Merge: Respostas dos 2 Agentes` | ✅ |
| AI Agent node (3º agente) com LLM e Tool | `Agente Supervisor (n8n)` + `query_support_policy` | ✅ |
| Sub-workflow reutilizável | `tp4_subworkflow_sla_calculator.json` | ✅ |
| Permissões por agente | `agent1/settings.json`, `agent2/settings.json` | ✅ |
| Hooks PreToolUse / PostToolUse | `agent1/hooks/`, `agent2/hooks/` | ✅ |
| Skills e subagentes | `SKILL.md`, `subagents/` | ✅ |
| Gatilho único (chatbot) | `chatbot/app.py` | ✅ |
| Link do GitHub | Topo de todos os relatórios | ✅ |
| Vídeo de até 5 min | Roteiro pronto; gravação pelo aluno | ⏳ |

---

## 7. Como executar

```bash
source .venv/bin/activate
uvicorn agent1.app:app --host 0.0.0.0 --port 8001     # terminal 1
uvicorn agent2.app:app --host 0.0.0.0 --port 8002     # terminal 2
python chatbot/run_chainlit.py run chatbot/app.py -w   # terminal 3 → http://localhost:8000
```

No n8n (`http://localhost:5678`):
1. importe primeiro `workflows/tp4_subworkflow_sla_calculator.json` e publique;
2. importe `workflows/tp4_main_orchestration_workflow.json`, confira o ID do sub-workflow no nó *Executar Sub-workflow de SLA* e a Data Table `helpdesk_tickets`;
3. configure a credencial do nó *Modelo LLM (Proxy 9Router)* e publique.

Teste rápido sem chatbot:

```bash
curl -X POST http://localhost:5678/webhook/helpdesk-triage-tp4 -H "Content-Type: application/json" \
  -d '{"user_prompt":"Minha conta está bloqueada, erro 403 na folha. maria.souza@empresa.com","session_id":"demo"}'
# → 202 {"ticket_id":"TCK-...","status":"processing", ...}   (responde na hora)

curl "http://localhost:5678/webhook/helpdesk-status?ticket_id=TCK-..."
# → {"status":"processing","stage":"triage_done"}  ...depois...  {"status":"done","result":{...}}
```

---

## 8. Vídeo de demonstração

O roteiro detalhado (o que mostrar e o que falar em cada minuto) é entregue à parte, junto com este relatório.

**Link do vídeo:** _([Tp4 - IT HELPDESK](https://youtu.be/Ns615Y2H_-U))_

---
