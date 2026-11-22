> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# AGENTS.md: Agente 2, Auto-Remediação e Despacho N2

> **Escopo deste documento:** comportamento, papel e restrições **somente do Agente 2**.
> As tarefas estão em [`TASK.md`](TASK.md) e as ferramentas em [`TOOLS.md`](TOOLS.md).
> De onde vêm os dados de entrada (Agente 1, Supervisor) é responsabilidade do n8n e não faz parte deste contrato.

| Campo | Valor |
| :--- | :--- |
| Nome | `IT_Remediation_N2_Agent` |
| Versão | API `1.1.0` · prompt `v3-tp5` |
| Serviço | FastAPI, porta **8002** (`uvicorn agent2.app:app --port 8002`) |
| Arquitetura | **Política determinística** (`plan_actions`) + ferramentas Python com hook `PostToolUse` + **LLM só como redator** do resumo |
| Modelo | `AG-DPS-CLAUDE-SONNET` via `MODEL_NAME` (proxy 9Router), `temperature=0.1`, `response_format=json_object` |
| Responsável | João Pedro Barboza |

---

## 1. Papel

O Agente 2 **executa ações privilegiadas** de TI a partir de dados **estruturados**:

- desbloqueio de conta no Active Directory;
- rota de contingência de VPN;
- abertura de incidente no ITSM com SLA.

Ele devolve um relatório auditável (`RemediationResponse`) com cada ação, seu status, os códigos de auditoria e os hashes de compliance.

## 2. Comportamento esperado

1. **Recebe** `RemediationRequest` em `POST /run`, valida o contrato (ver §4) e responde `202` com `task_id`.
2. **Decide** as ações com `plan_actions()`, uma função pura e testável que usa **somente** campos estruturados:

   | Ordem | Condição | Ações |
   | :-: | :--- | :--- |
   | 1 | `requires_human_escalation = true` | `DISPATCH_INCIDENT` apenas. Se a triagem pediu um humano, o Agente 2 não age sobre a conta. |
   | 2 | `action_type` ∈ {`UNLOCK_ACCOUNT`, `VPN_FAILOVER`, `DISPATCH_INCIDENT`} | a ação indicada |
   | 3 | `action_type` = `AUTO_DETECT` ou ausente | pela categoria: `Acessos/Senhas`→unlock · `Redes/VPN`→failover · demais→dispatch |
   | 4 | ação sobre conta ou VPN **sem** `user_email` | troca por `DISPATCH_INCIDENT` (fallback seguro) |

3. **Executa** as ferramentas. Cada retorno passa pelo hook `PostToolUse`, que acrescenta `compliance_hash` (SHA-256) e grava `hooks/security_audit.log`.
4. **Consolida** os resultados:
   - `status`: `SUCCESS` · `PARTIAL` · `ESCALATED` · `REJECTED`, calculado das ações;
   - `sla_target_minutes`: da matriz oficial;
   - `escalation_team`: da tabela categoria → equipe;
   - `audit_trail`: começa com `POLICY: <motivo da decisão>`.
5. **Redige** o `resolution_summary` com o LLM. O modelo recebe os fatos e **não pode** alterar status, SLA, equipe ou ações. Se o LLM falhar, o resumo vem de template e `summary_source="template"`.
6. **Registra** cada execução em `execution_log.jsonl` (JSON Lines, append-only) com `prompt_version`. O `execution_log.json` antigo fica como histórico do TP3/TP4.

## 3. Restrições (o que o Agente 2 **não** faz)

| # | Restrição | Como é garantida |
| :-: | :--- | :--- |
| R1 | Não processa linguagem natural para decidir. `recommended_action` é **informação**, nunca comando. | `plan_actions()` ignora o texto livre. Teste `test_policy_ignores_free_text_keywords`. |
| R2 | Não age sobre contas fora de `@empresa.com` | `RemediationRequest` rejeita (`422`), e as ferramentas recusam também (defesa em profundidade) |
| R3 | Não "desbloqueia" conta inexistente nem conta já ativa | `unlock_user_account` → `FAILED (NOT_FOUND)` / `SKIPPED (ALREADY_ACTIVE)` |
| R4 | Não desbloqueia quando a triagem pediu humano | Regra 1 da política (teste RT-01) |
| R5 | Não inventa SLA nem equipe | SLA vem de `SLA_MATRIX_MINUTES` (Critica 30, Alta 120, Media 480, Baixa 1440) e equipe de `TEAM_BY_CATEGORY`. O LLM não tem acesso de escrita a esses campos. |
| R6 | Não usa gateway de VPN fora da lista aprovada | `APPROVED_VPN_GATEWAYS = {"BR-SA-02"}` |
| R7 | Não se comunica com o Agente 1 | Não há cliente HTTP para o Agente 1. A integração é do n8n. |
| R8 | Não aceita chamadas sem autenticação quando `AGENT2_API_TOKEN` está definido | `require_api_key` (header `X-API-Key`) em `/run` e `/status` |
| R9 | Não fica preso em uma tarefa | Timeout `AGENT2_TASK_TIMEOUT_SECONDS` (padrão 100 s), que termina em `status=error` |

## 4. Contratos de interface

| Endpoint | Entrada | Saída | Códigos |
| :--- | :--- | :--- | :--- |
| `POST /run` | `RemediationRequest` (ver `TASK.md` §T1) | `TaskInitiatedResponse {task_id: "rem_task_…", status, message}` | `202` · `401` · `422` |
| `GET /status/{task_id}` | — | `TaskStatusResponse {task_id, status: pending\|done\|error, created_at, completed_at, result: RemediationResponse?, error?}` | `200` · `401` · `404` |
| `GET /health` | — | `{status, version, prompt_version, auth_enabled, active_tasks_count}` | `200` |

## 5. Governança

- **Permissões do Claude Code:** [`settings.json`](settings.json).
  - `deny`: remover logs de auditoria, ler `.env`, editar o hook.
  - `ask`: `models.py`, `runner.py`, `tools.py`, `security.py`.
- **Hook `PostToolUse`:** [`hooks/post_tool_auditor.py`](hooks/post_tool_auditor.py). Gera `compliance_hash = "SEC-" + SHA-256(ação, args, resultado, timestamp)[:16]` e grava em `hooks/security_audit.log`, append-only.
- **Skill:** [`SKILL.md`](SKILL.md) (`sla-incident-dispatch`).
- **Subagente:** [`subagents/sla_auditor.md`](subagents/sla_auditor.md) (`sla-compliance-auditor`).
- **Testes:**
  - `python -m pytest agent2/test_agent2_unit.py` (26 casos, sem LLM);
  - `python agent2/test_agent2_api.py`.
