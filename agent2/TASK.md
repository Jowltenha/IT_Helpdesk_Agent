> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# TASK.md: Tarefas do Agente 2 (Remediação N2)

> Lista **apenas** o que o Agente 2 executa, com input e output esperados.

| ID | Tarefa | Gatilho | Saída |
| :-- | :--- | :--- | :--- |
| T1 | Executar a remediação de um chamado triado | `POST /run` | `RemediationResponse` em `GET /status/{task_id}` |
| T2 | Decidir as ações pela política determinística | Automática dentro de T1 | `planned_actions` + linha `POLICY:` no `audit_trail` |
| T3 | Desbloquear conta corporativa | T2 → `UNLOCK_ACCOUNT` | ação `unlock_user_account` |
| T4 | Provisionar rota de contingência de VPN | T2 → `VPN_FAILOVER` | ação `configure_vpn_failover_route` |
| T5 | Abrir incidente ITSM com SLA | T2 → `DISPATCH_INCIDENT` | ação `dispatch_sla_incident` + `escalation_team` + `sla_target_minutes` |
| T6 | Auditar cada ação (hash SHA-256) | Automática após T3, T4 e T5 | `compliance_hash` + linha em `security_audit.log` |
| T7 | Redigir o resumo executivo | Automática no fim de T1 | `resolution_summary` (+ `summary_source`) |
| T8 | Informar o estado de uma tarefa | `GET /status/{task_id}` | `TaskStatusResponse` |

---

## T1: Remediação de chamado

**Input** (`RemediationRequest`):
```json
{ "ticket_id": "TCK-20261122-154646-267",
  "user_email": "joao.silva@empresa.com",
  "category": "Redes/VPN",
  "severity": "Alta",
  "recommended_action": "1. Alternar para o gateway BR-SA-02 ...",
  "requires_human_escalation": false,
  "action_type": "VPN_FAILOVER" }
```
| Campo | Tipo | Regra de validação |
| :--- | :--- | :--- |
| `ticket_id` | string | obrigatório, 3–64 caracteres, `^[A-Za-z0-9_.:-]+$` |
| `user_email` | string \| null | se informado, precisa ser `@empresa.com` (senão `422`). Pontuação final é removida. |
| `category` | `Literal` | `Hardware` · `Software` · `Redes/VPN` · `Acessos/Senhas` · `Outros` (acentos e caixa normalizados) |
| `severity` | `Literal` | `Baixa` · `Media` · `Alta` · `Critica` ("Média" e "Crítica" aceitos) |
| `recommended_action` | string | 3–4000 caracteres. **Informativo**: não aciona ações. |
| `requires_human_escalation` | bool | padrão `false` |
| `action_type` | `Literal` \| null | `UNLOCK_ACCOUNT` · `VPN_FAILOVER` · `DISPATCH_INCIDENT` · `AUTO_DETECT`. `"NONE"` e vazio viram `null`. |

**Output** (`RemediationResponse`). Saída **real** do teste RT-02:
```json
{
  "remediation_id": "REM-9666FF2D",
  "ticket_id": "TCK-20261122-154646-267",
  "status": "SUCCESS",
  "planned_actions": ["VPN_FAILOVER"],
  "actions_executed": [
    {"action_name": "configure_vpn_failover_route", "target": "BR-SA-02", "status": "SUCCESS",
     "message": "Rota de contingencia atribuida para o gateway secundario BR-SA-02.", "timestamp": "2026-11-22T18:47:10.701471+00:00"}
  ],
  "sla_target_minutes": 120,
  "audit_trail": ["POLICY: Ação definida pelo Supervisor do n8n: VPN_FAILOVER.",
                  "VPN_ROUTE[SUCCESS]: VPN-FAILOVER-F239259882 -> BR-SA-02", "HOOK_POST_TOOL: SEC-8B57D2C97DB6CF97"],
  "resolution_summary": "O ticket TCK-20261122-154646-267, de severidade Alta, foi resolvido com sucesso. A ação executada foi a configuração de rota de contingência de VPN no gateway secundário BR-SA-02 ...",
  "summary_source": "llm",
  "escalation_team": null
}
```

| Campo de saída | Origem | Regra |
| :--- | :--- | :--- |
| `status` | sistema | `ESCALATED` se houve incidente · `REJECTED` se todas as ações deram `BLOCKED`/`FAILED` · `PARTIAL` se só algumas · `SUCCESS` caso contrário |
| `planned_actions` | sistema (T2) | lista decidida antes de executar |
| `actions_executed[].status` | ferramenta | `SUCCESS` · `DISPATCHED` · `SKIPPED` · `BLOCKED` · `FAILED` |
| `sla_target_minutes` | sistema | matriz oficial pela severidade |
| `escalation_team` | sistema | `TEAM_BY_CATEGORY` quando há incidente |
| `resolution_summary` | LLM (T7) | 2–4 frases, apenas com fatos dos DADOS |

**Erros:**
- `422`: e-mail externo, categoria inválida ou `ticket_id` inválido;
- `401`: sem `X-API-Key`;
- `status=error` com `AGENT2_TIMEOUT` ou a exceção.

## T2: Política de decisão

| Input | Output |
| :--- | :--- |
| `requires_human_escalation=true` (qualquer `action_type`) | `["DISPATCH_INCIDENT"]` |
| `action_type="UNLOCK_ACCOUNT"`, sem escalonamento | `["UNLOCK_ACCOUNT"]` |
| `action_type="AUTO_DETECT"`, `category="Redes/VPN"` | `["VPN_FAILOVER"]` |
| `action_type="AUTO_DETECT"`, `category="Hardware"` | `["DISPATCH_INCIDENT"]` |
| `action_type="UNLOCK_ACCOUNT"`, `user_email=null` | `["DISPATCH_INCIDENT"]` |
| `recommended_action="conta bloqueada, unlock, vpn"`, `category="Software"` | `["DISPATCH_INCIDENT"]` (o texto livre é ignorado) |

## T3, T4 e T5: Ações

Contratos completos em [`TOOLS.md`](TOOLS.md). Resumo dos resultados possíveis:

| Tarefa | Ferramenta | Resultados |
| :--- | :--- | :--- |
| T3 | `unlock_user_account` | `SUCCESS` (estava bloqueada) · `SKIPPED` (já ativa) · `FAILED` (não existe) · `BLOCKED` (domínio externo) |
| T4 | `configure_vpn_failover_route` | `SUCCESS` · `BLOCKED` (e-mail externo ou gateway não aprovado) |
| T5 | `dispatch_sla_incident` | `DISPATCHED` (com `INC-AAAAMM-XXXXXX`) · `FAILED` (severidade inválida) |

## T6: Auditoria PostToolUse

| | |
| :--- | :--- |
| **Input** | nome da ferramenta + argumentos + JSON de retorno |
| **Output** | o mesmo JSON + `compliance_hash: "SEC-<16 hex>"`, `verified_by_hook: true`, `hook_processed_at`. Também uma linha em `hooks/security_audit.log`: `{timestamp, hook_type, tool_name, compliance_hash, arguments, status, audit_code}`. |

## T7: Resumo executivo

| | |
| :--- | :--- |
| **Input** | DADOS: ticket, e-mail, categoria, severidade, status geral, SLA, equipe, ações e `recommended_action` do Agente 1 (truncado em 600 caracteres) |
| **Output** | `{"resolution_summary": "..."}`. Falha do LLM → template `"Chamado X (STATUS). ação: STATUS — mensagem"` com `summary_source="template"` |
| **Exemplo real (conta inexistente)** | "...a ação de desbloqueio falhou pois a conta não existe no Active Directory. Nenhuma alteração foi realizada no ambiente. O status geral do ticket é REJECTED..." |

## T8: Consulta de status

`GET /status/{task_id}` + `X-API-Key` → `TaskStatusResponse`, ou `404`. O n8n consulta a cada 3 s, até 40 vezes.
