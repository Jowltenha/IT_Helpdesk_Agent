# CLAUDE.md: Agente 2, Auto-Remediação e Despacho N2 (estado final, TP5)

> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent
>
> Contexto para o Claude Code quando ele trabalha **dentro de `agent2/`**. Estratégia: **Inverted Pyramid + Constraint Anchoring**: primeiro o que nunca pode quebrar, depois os detalhes.
> Contratos formais: [`AGENTS.md`](AGENTS.md) · [`TASK.md`](TASK.md) · [`TOOLS.md`](TOOLS.md).

---

## 1. Âncoras de restrição (ler antes de qualquer mudança)

1. **O Agente 2 executa ações privilegiadas.** Quem decide é código determinístico (`runner.py::plan_actions`), **nunca** o LLM e **nunca** o texto livre `recommended_action`.
2. **O LLM só redige `resolution_summary`.** Não deixe o modelo escrever `status`, `sla_target_minutes`, `escalation_team` ou `actions_executed`. No TP4 ele inventava SLA de 15 min e equipes como "SOC-TIER2-SECURITY-FORENSICS".
3. **`requires_human_escalation=true` ⇒ só `DISPATCH_INCIDENT`.** Não desbloqueie conta quando a triagem pediu um humano (ex.: KB-104, confirmação de identidade por telefone).
4. **Somente `@empresa.com`.** O contrato (`RemediationRequest`) rejeita com `422`, e as ferramentas recusam de novo com `BLOCKED`. Mantenha as duas camadas.
5. **Recusa explícita, nunca sucesso falso.** Conta inexistente → `FAILED`; conta já ativa → `SKIPPED`. Não reintroduza o "desbloqueio de contingência".
6. **Toda ferramenta passa pelo hook `PostToolUse`** (hash SHA-256 + `security_audit.log`). Os logs de auditoria são append-only: não apague nem reescreva.
7. **Não conhece o Agente 1.** A integração é do n8n.

## 2. Estrutura

```
agent2/
├── app.py            # FastAPI :8002 — POST /run (202), GET /status/{id}, GET /health; X-API-Key; timeout por tarefa
├── runner.py         # plan_actions() + execução das tools + _summarize() (LLM redator) + execution_log.jsonl (append-only)
├── models.py         # RemediationRequest estrito (Literal, e-mail corporativo), RemediationAction, RemediationResponse
├── tools.py          # unlock_user_account, configure_vpn_failover_route, dispatch_sla_incident (+ SLA_MATRIX_MINUTES)
├── security.py       # require_api_key (AGENT2_API_TOKEN)
├── hooks/post_tool_auditor.py   # PostToolUse: compliance_hash + hooks/security_audit.log
├── test_agent2_unit.py          # 26 testes offline (pytest)
├── test_agent2_api.py           # ciclo HTTP
├── settings.json · SKILL.md · subagents/sla_auditor.md
└── AGENTS.md · TASK.md · TOOLS.md · CLAUDE.md
```

## 3. Regras de código

- **Nova ação?** Na ordem: adicione o valor ao `ActionType`, a regra em `plan_actions()` com teste, a ferramenta com hook e recusa explícita, a linha em `TOOLS.md` e o caso em `tests/run_regression.py`.
- **Matriz de SLA** (`SLA_MATRIX_MINUTES`): Critica 30 · Alta 120 · Media 480 · Baixa 1440. Precisa ser **igual** à do sub-workflow n8n (`Calcular SLA e Equipe`). Se mudar uma, mude a outra.
- **Normalização:** severidade e categoria sem acento (`Média`→`Media`). E-mail em minúsculas e sem pontuação final.
- **Prompt do redator** (`AGENT2_SYSTEM_PROMPT`, `v3-tp5`): só fatos do bloco DADOS; ações `BLOCKED`/`FAILED`/`SKIPPED` são descritas como não executadas. Ao mudar, incremente `PROMPT_VERSION`.
- **Segredos:** `.env` da raiz (`AGENT2_API_TOKEN`). Nunca leia nem imprima.

## 4. Comandos

```bash
source .venv/bin/activate
uvicorn agent2.app:app --host 0.0.0.0 --port 8002
python -m pytest agent2/test_agent2_unit.py -q           # 26 testes offline
python tests/run_regression.py --with-outage             # inclui RT-06 (Agente 2 fora do ar)
```

## 5. Histórico de mudanças relevantes (TP5)

| Mudança | Comportamento observado que motivou (logs reais) |
| :--- | :--- |
| `plan_actions()` determinística no lugar de substrings no texto | 7/7 execuções do TP4 desbloquearam a conta mesmo com escalonamento; "rede" em "**rede**finição" mandava para N2 Infraestrutura (4/7) |
| LLM restrito ao resumo | SLA de 15 min (fora da matriz) e equipes inventadas pelo LLM |
| `RemediationRequest` estrito | `atacante@gmail.com` gerava `unlock: SUCCESS`; "Média" gerava SLA de 240 min |
| `unlock_user_account` com `FAILED`/`SKIPPED` | Conta inexistente e `maria.souza@empresa.com.` recebiam "desbloqueio de contingência" com `SUCCESS` |
| `user_email` opcional + fallback para dispatch | Sem e-mail, o n8n enviava `nao.informado@empresa.com` |
| X-API-Key + timeout | API aberta a qualquer cliente na rede; tarefa podia ficar `pending` indefinidamente |
| **Rodada 2 (revisão do Claude Code nesta pasta):** matriz `action_type × category` | O Supervisor podia pedir `UNLOCK_ACCOUNT` para Hardware |
| Fallback: ação automática `FAILED`/`BLOCKED` → incidente | Conta inexistente terminava `REJECTED` sem dono (chamado órfão) |
| Idempotência por `ticket_id` (API e ITSM) | O `retryOnFail` do n8n poderia duplicar o incidente `INC-` |
| VPN valida conta no AD; `ticket_id` e `audit_code` em toda auditoria | `nao.existe@empresa.com` receberia rota com `SUCCESS` |
| Redator v3 sem o texto do Agente 1 e com nomes literais | O resumo repetia alegações não verificadas ("grupo já atribuído") e dizia "resolvido" |
| Log `execution_log.jsonl` append-only | O JSON era reescrito a cada execução (contradizia a âncora 6) |

Detalhes e evidências: [`relatorios/RELATORIO_TECNICO_TP5.md`](../relatorios/RELATORIO_TECNICO_TP5.md) §1.2.
