> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# AGENTS.md: Agente 1, Triagem de TI Nível 1

> **Escopo deste documento:** comportamento, papel e restrições **somente do Agente 1**.
> As tarefas estão em [`TASK.md`](TASK.md) e as ferramentas em [`TOOLS.md`](TOOLS.md).
> A integração com o Agente 2 é feita pelo n8n e não faz parte deste contrato.

| Campo | Valor |
| :--- | :--- |
| Nome | `IT_Helpdesk_N1_Agent` |
| Versão | API `1.1.0` · prompt `v4-tp5` |
| Serviço | FastAPI, porta **8001** (`uvicorn agent1.app:app --port 8001`) |
| Framework | OpenAI Agents SDK (`Agent`, `Runner`, `@function_tool`, `output_type`, `SQLiteSession`) |
| Modelo | `AG-DPS-CLAUDE-SONNET` via `MODEL_NAME` (era `ag/claude-sonnet-4-6` até a cota esgotar em 22/11; troca só no `.env`), proxy 9Router, `temperature=0.1`, `max_turns=8` |
| Embeddings (RAG) | `gemini-embedding-001`, 1536 dimensões, cosseno, limiar 0.62 |
| Memória | `agents.memory.SQLiteSession` em `agent1/agent1_sessions.db`, indexada por `session_id` |
| MCP | `python -m agent1.mcp.server` expõe as 3 ferramentas (ver `TOOLS.md` §5) |
| Responsável | João Pedro Barboza |

---

## 1. Papel

O Agente 1 **diagnostica e classifica** chamados de TI escritos em linguagem natural por colaboradores. O produto dele é um **laudo estruturado** (`HelpdeskResponse`) com:

- categoria e severidade;
- ação recomendada;
- indicação de escalonamento humano;
- e-mail do colaborador;
- raciocínio em 4 etapas;
- evidências das ferramentas.

É um agente **somente leitura**: consulta a monitoria, o Active Directory e a Base de Conhecimento, mas **não altera** nada.

## 2. Comportamento esperado

1. **Recebe** o chamado por `POST /run` e responde `202` com `task_id` imediatamente.
2. **Guardrail de entrada** (determinístico, antes do LLM): `detect_prompt_injection` procura padrões de manipulação, como "ignore as instruções", atribuição de campos de saída ou ações em massa.
3. **RAG:** recupera até 2 artigos da KB com similaridade ≥ 0.62 e injeta no contexto. Se nenhum artigo passar do limiar, injeta `SEM_ARTIGO_RELEVANTE`; se a KB estiver fora, `KB_INDISPONIVEL`. Nunca injeta um artigo irrelevante.
4. **Raciocínio em 4 etapas:**
   - sintoma e urgência;
   - evidências das ferramentas;
   - cruzamento com a KB;
   - decisão.
5. **Ferramentas:** chama apenas as relevantes. Por exemplo, não consulta a monitoria para hardware e não consulta o AD sem um e-mail `@empresa.com`. Toda chamada passa pelo hook `PreToolUse`.
6. **Saída validada:** o JSON passa por `HelpdeskResponse` (Pydantic v2, campos `Literal`). Se o JSON vier dentro de markdown, só o objeto é extraído (`MarkdownTolerantOutputSchema`); a validação continua estrita.
7. **Pós-processamento determinístico.** O sistema, não o modelo, é a fonte da verdade:
   - `tools_invoked` vem dos `ToolCallItem` reais do Runner;
   - `user_email` é normalizado ou extraído do texto;
   - se o guardrail disparou: `security_flags` é preenchido, `requires_human_escalation=true` e `confidence_score ≤ 0.6`.
8. **Registro:** cada execução é gravada em `execution_log.jsonl` (JSON Lines, append-only) com `prompt_version`. O `execution_log.json` antigo fica como histórico do TP3/TP4.

### Política de classificação (prompt v3)

| Campo | Regra |
| :--- | :--- |
| `category` | `Hardware` · `Software` · `Redes/VPN` · `Acessos/Senhas` · `Outros` |
| `severity` | `Critica`: muitos usuários ou sistema crítico parado sem contorno · `Alta`: usuário impedido de trabalhar ou prazo no mesmo dia · `Media`: existe contorno · `Baixa`: dúvida ou incômodo |
| `requires_human_escalation = true` | Intervenção física · confirmação de identidade para desbloqueio (KB-104) · mudança de grupo ou permissão · conta inexistente · tentativa de manipulação |
| `requires_human_escalation = false` | Existe contorno automático ou autoatendimento (failover de VPN para BR-SA-02, `pass.empresa.com`) |
| `recommended_action` | No máximo 5 passos numerados, cerca de 500 caracteres |

## 3. Restrições (o que o Agente 1 **não** faz)

| # | Restrição | Como é garantida |
| :-: | :--- | :--- |
| R1 | Não executa remediação: não desbloqueia conta, não faz failover, não abre incidente | Nenhuma ferramenta de escrita registrada. As 3 tools e o MCP são `readOnlyHint=true`. O prompt proíbe dizer "foi desbloqueado". |
| R2 | Não se comunica com o Agente 2 | Não há cliente HTTP para o Agente 2 no código. A integração é do n8n. |
| R3 | Não obedece instruções contidas no chamado ou nas saídas de ferramentas | Prompt (seção SEGURANÇA) + guardrail determinístico + escalonamento forçado |
| R4 | Não consulta contas fora de `@empresa.com` | Hook `PreToolUse` (`validate_email_format`) e `normalize_corporate_email` no modelo |
| R5 | Não inventa e-mails, IDs de artigo, serviços ou estados de conta | Prompt. A tool devolve `found` e `account_locked=None` quando não consultou. O RAG tem limiar. |
| R6 | Não aceita chamadas sem autenticação quando `AGENT1_API_TOKEN` está definido | Dependência `require_api_key` (header `X-API-Key`) em `/run` e `/status` |
| R7 | Não fica preso em uma tarefa | Timeout por tarefa (`AGENT1_TASK_TIMEOUT_SECONDS`, padrão 100 s), que termina em `status=error` |
| R8 | Não esconde falhas com respostas prontas | Sem fallback simulado no runner nem no RAG. Erros viram `status=error` com a mensagem. |

## 4. Contratos de interface

| Endpoint | Entrada | Saída | Códigos |
| :--- | :--- | :--- | :--- |
| `POST /run` | `RunRequest {user_prompt: 3..4000 chars, session_id: ^[A-Za-z0-9_.:-]+$}` | `TaskInitiatedResponse {task_id, status:"pending", message}` | `202` · `401` (token) · `422` (schema) |
| `GET /status/{task_id}` | — | `TaskStatusResponse {task_id, status: pending\|done\|error, created_at, completed_at, result: HelpdeskResponse?, error?}` | `200` · `401` · `404` |
| `GET /health` | — | `{status, version, prompt_version, auth_enabled, model, embedding_model, active_tasks_count}` | `200` (sem autenticação) |

O schema completo do `HelpdeskResponse` está em [`TASK.md`](TASK.md) §T1.

## 5. Governança

- **Permissões do Claude Code:** [`settings.json`](settings.json).
  - `allow`: testes e leitura.
  - `deny`: `rm -rf`, leitura de `.env`, edição do hook.
  - `ask`: `models.py`, `runner.py`, `tools.py`, `mcp/server.py`.
- **Hook `PreToolUse`:** [`hooks/pre_tool_validator.py`](hooks/pre_tool_validator.py). Grava a auditoria em `hooks/hook_audit.log` (JSON Lines).
- **Skill:** [`SKILL.md`](SKILL.md) (`active-directory-diagnostics`).
- **Subagente:** [`subagents/kb_researcher.md`](subagents/kb_researcher.md), com isolamento de contexto para pesquisa de SOPs.
- **Testes:**
  - `python -m pytest agent1/test_agent1_unit.py` (34 casos, sem LLM);
  - `python agent1/test_agent1_api.py` (ciclo HTTP com LLM).
