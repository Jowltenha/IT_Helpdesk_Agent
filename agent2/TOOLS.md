> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# TOOLS.md: Ferramentas do Agente 2 (Remediação N2)

> Contrato formal de entrada e saída de **cada ferramenta do Agente 2** ([`tools.py`](tools.py)).
> São ferramentas **com efeito colateral** (escrita). Por isso:
> - quem as chama é a política determinística do runner, nunca o LLM;
> - todas passam pelo hook `PostToolUse`.

## Regras comuns

| Regra | Detalhe |
| :--- | :--- |
| Escrita controlada | Chamadas somente por `RemediationAgentRunner.run()` conforme `plan_actions()`. O LLM não tem acesso às ferramentas. |
| Validação em duas camadas | 1) `RemediationRequest` (Pydantic) na API. 2) Cada ferramenta revalida domínio, gateway e severidade (defesa em profundidade). |
| Recusa explícita | Entrada inválida não lança exceção: retorna `status` `BLOCKED` ou `FAILED` com `message`, e a recusa também é auditada. |
| Hook `PostToolUse` | Todo retorno ganha `compliance_hash` (`SEC-` + 16 hex do SHA-256), `verified_by_hook: true` e `hook_processed_at`, e gera uma linha em `hooks/security_audit.log`. |
| Formato | Todas retornam **string JSON** (compatível com `@function_tool`). O runner converte para `RemediationAction`. |
| Dados | AD e ITSM **simulados** em memória (`MOCK_AD_ACCOUNTS`, `MOCK_ITSM_TICKETS`). `reset_mock_state()` restaura o estado nos testes. |

---

## 1. `unlock_user_account`

Desbloqueia uma conta corporativa existente e zera as falhas de login.

**Entrada:**

| Campo | Tipo | Obrigatório | Restrições |
| :--- | :--- | :-: | :--- |
| `user_email` | string | sim | precisa terminar em `@empresa.com`; normalizado (minúsculas, sem pontuação final) |
| `reason` | string | não | motivo ou ticket de auditoria (padrão `"Solicitacao automatizada via Helpdesk"`) |

**Saída:**

| Campo | Tipo | Valores |
| :--- | :--- | :--- |
| `operation` | string | `UNLOCK_USER_ACCOUNT` |
| `email` | string | normalizado |
| `status` | enum | `SUCCESS` · `SKIPPED` · `FAILED` · `BLOCKED` |
| `previous_state` / `current_state` | enum | `LOCKED`→`ACTIVE` · `ACTIVE`→`ACTIVE` · `NOT_FOUND` · `N/A` |
| `audit_code` | string | `AUDIT-AD-XXXXXXXX` |
| `message`, `timestamp` | string | detalhe e horário ISO 8601 |
| `compliance_hash`, `verified_by_hook`, `hook_processed_at` | — | adicionados pelo hook |

**Matriz de comportamento:**

| Situação | status | Efeito no AD |
| :--- | :--- | :--- |
| Conta existe e está bloqueada | `SUCCESS` | `account_locked=false`, `failed_attempts=0` |
| Conta existe e já está ativa | `SKIPPED` | nenhum (idempotente) |
| Conta não existe | `FAILED` | nenhum. No TP4 retornava `SUCCESS`, o "desbloqueio de contingência". |
| Domínio externo | `BLOCKED` | nenhum |

## 2. `configure_vpn_failover_route`

Atribui ao usuário a rota de contingência da VPN corporativa.

**Entrada:**

| Campo | Tipo | Obrigatório | Restrições |
| :--- | :--- | :-: | :--- |
| `user_email` | string | sim | `@empresa.com` |
| `gateway` | string | não (padrão `BR-SA-02`) | precisa estar em `APPROVED_VPN_GATEWAYS = {"BR-SA-02"}` |

**Saída:**

| Campo | Tipo | Valores |
| :--- | :--- | :--- |
| `operation` | string | `CONFIGURE_VPN_FAILOVER_ROUTE` |
| `email`, `target_gateway` | string | normalizados |
| `status` | enum | `SUCCESS` · `BLOCKED` |
| `session_token` | string \| null | `VPN-FAILOVER-XXXXXXXXXX` quando `SUCCESS` |
| `dns_servers` | string[] | `["10.0.0.10","10.0.0.11"]` quando `SUCCESS` |
| `message`, `timestamp` | string | — |

## 3. `dispatch_sla_incident`

Registra um incidente no ITSM e calcula o SLA pela matriz oficial.

**Entrada:**

| Campo | Tipo | Obrigatório | Restrições |
| :--- | :--- | :-: | :--- |
| `ticket_id` | string | sim | chamado de origem |
| `severity` | string | sim | `Critica` · `Alta` · `Media` · `Baixa`, com ou sem acento e em qualquer caixa |
| `team` | string | sim | equipe responsável. O runner usa `TEAM_BY_CATEGORY`. |
| `justification` | string | sim | truncada em 500 caracteres |

**Matriz de SLA** (`SLA_MATRIX_MINUTES`, igual à do sub-workflow do n8n):

| Severidade | Crítica | Alta | Média | Baixa |
| :--- | :-: | :-: | :-: | :-: |
| SLA (min) | 30 | 120 | 480 | 1440 |

**Equipes** (`TEAM_BY_CATEGORY`, definidas no runner):

| Categoria | Equipe |
| :--- | :--- |
| `Acessos/Senhas` | N2 Acessos e Identidade |
| `Redes/VPN` | N2 Infraestrutura e Redes |
| `Hardware` | Suporte Presencial N2 |
| `Software` | N2 Aplicacoes |
| `Outros` | N1 Suporte Geral |

**Saída (sucesso):**
```json
{"incident_number":"INC-202611-3D5477","original_ticket_id":"TCK-…","assigned_team":"N2 Acessos e Identidade",
 "severity":"Alta","sla_target_minutes":120,"on_call_engineer":"Plantao_N2_Engenharia","status":"DISPATCHED",
 "justification":"…","dispatched_at":"2026-11-22T18:46:40+00:00","compliance_hash":"SEC-…","verified_by_hook":true}
```

**Saída (severidade inválida):** `{"status":"FAILED","incident_number":null,"sla_target_minutes":null,"message":"Severidade 'X' invalida; use Critica, Alta, Media ou Baixa."}`. No TP4, "Média" com acento gerava um SLA de 240 min, fora da matriz.

---

## 4. Hook `PostToolUse` (`hooks/post_tool_auditor.py`)

| Entrada | Saída |
| :--- | :--- |
| `tool_name`, `tool_args` (dict), `tool_result_raw` (string JSON) | o mesmo JSON + `compliance_hash`, `verified_by_hook`, `hook_processed_at`. Também grava em `security_audit.log`: `{timestamp, hook_type:"PostToolUse", tool_name, compliance_hash, arguments, status, audit_code}` |

`compliance_hash = "SEC-" + SHA256(f"{tool}::{args}::{result}::{timestamp}")[:16].upper()`
