> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# Workflows n8n: Orquestração Multi-Agente (TP3 → TP5)

Os workflows do **n8n** orquestram, de forma assíncrona e desacoplada, o **Agente 1 (Triagem N1, :8001)** e o **Agente 2 (Remediação N2, :8002)**. No TP5 o sistema passou a ter **error handling com Error Trigger**, **configuração e segredos fora do código** e **testes regressivos**.

| Arquivo | Workflow no n8n | ID | Status |
| :--- | :--- | :--- | :--- |
| **`tp5_main_orchestration_workflow.json`** | TP5 - Orquestracao Multi-Agente (Helpdesk) com Error Handling | `wt8HmLdSFt9VQT51` | publicado (34 nós) |
| **`tp5_error_handler_workflow.json`** | TP5 - Error Handler: Alertas do Helpdesk | `XTwrw7QKUh7netfC` | publicado (7 nós: Error Trigger + webhook de consulta) |
| **`tp5_subworkflow_sla_calculator.json`** | TP4 - Sub-workflow: Calculadora de SLA | `BPDzhhNbkyZ4VDoI` | publicado (5 nós) |
| `tp4_*.json`, `tp3_*.json` | Versões históricas | — | referência |

---

## 1. Fluxo principal (TP5)

```text
Chatbot ─POST /webhook/helpdesk-triage-tp4─► Normalizar ► Registrar (processing) ► Responder 202 ──► (chatbot liberado)
                                                                                     │
                       Carregar Configuracao (Data Table helpdesk_config) ► Montar Configuracao
                                                                                     │
  Disparar Agente 1 [X-API-Key, retry 2x] ─erro─┐                                    │
        │                                       │
  Wait 3s ► GET /status [retry 3x] ► Switch ─pending (< POLL_MAX_ATTEMPTS)─► volta ao Wait
                                        ├─done──► Triagem concluída ► Supervisor (AI Agent) ► If ► Agente 2 (mesmo laço)
                                        └─error/timeout─┐                                          │
                                                        ▼                                          ▼
                                   Preparar Mensagem de Erro ◄────────────────────────── erro/timeout do Agente 2
                                                        ▼
                                   Salvar Falha (status=error, stage=failed)
                                                        ▼
                                   Stop and Error  ──► dispara o ERROR WORKFLOW (settings.errorWorkflow)

  Merge (Agente 1 + Agente 2 ou "não necessário") ► Sub-workflow SLA ► Consolidar ► Salvar (done)
```

## 2. Error handling (Error Trigger)

O workflow principal tem `settings.errorWorkflow = XTwrw7QKUh7netfC`. **Qualquer** execução de produção que termine em erro aciona o Error Workflow:

- falha de um agente, transformada em erro pelo nó `Falha do Agente -> Error Workflow` (Stop and Error);
- erro inesperado em qualquer nó.

```text
Error Trigger ► Montar Alerta (Code) ► Notificar Discord (#helpdesk-alertas) ► Registrar Alerta (Data Table helpdesk_alerts)
```

O mesmo workflow tem um segundo gatilho, `GET /webhook/helpdesk-alerts` (Webhook ► Buscar Ultimos Alertas ► Responder). Ele devolve os 5 alertas mais recentes, que aparecem no chatbot no botão **"Ver alertas de falha (Error Workflow)"**.

| Nó | Função |
| :--- | :--- |
| `Montar Alerta` | Extrai `workflow`, `execution.id`/`url`, nó que falhou e mensagem. Lê `agent=agent1\|agent2` e `ticket=` da mensagem do Stop and Error para identificar **qual agente** falhou. |
| `Notificar Discord` | Webhook do Discord (credencial `Helpdesk Alertas - Discord Webhook`). `onError: continueRegularOutput`: se o Discord cair, o alerta ainda é gravado. |
| `Registrar Alerta` | Grava em `helpdesk_alerts`: `alert_id, created_at, workflow_name, execution_id, failed_node, agent, ticket_id, error_message, notified_channel` (`discord_OK` / `discord_FALHOU`). |

### Comportamento de fallback

| Falha | Detecção | O que o n8n faz | O que o usuário vê |
| :--- | :--- | :--- | :--- |
| Agente 1 fora do ar (conexão recusada / timeout HTTP) | `Disparar Agente 1` falha 2 vezes (`retryOnFail`, 2 s entre tentativas) → saída de erro | Ticket fica `error/failed` com a mensagem → Stop and Error → alerta `agent=agent1` | Chatbot: "❌ Erro no processamento do ticket …" com a mensagem. Se o **próprio n8n** estiver fora, o chatbot chama o Agente 1 direto (modo de contingência). |
| Agente 1 responde `status=error` (ex.: `AGENT1_TIMEOUT` após 100 s, falha do LLM) | Switch → `erro_ou_timeout` | idem | idem |
| Agente 1 não termina em `POLL_MAX_ATTEMPTS × 3 s` (2 min) | Switch: `$runIndex ≥ POLL_MAX_ATTEMPTS` → `erro_ou_timeout` | idem, com a mensagem "Tempo limite de polling excedido…" | idem |
| `GET /status` com erro transitório | `retryOnFail` 3× (1 s) e `neverError` (resposta não-2xx não derruba o nó) | segue o laço | nada |
| Agente 2 fora do ar / erro / timeout | mesmo tratamento, depois do laudo do Agente 1 | Ticket `error/failed` · alerta `agent=agent2` | Mensagem de erro; o laudo do Agente 1 fica no log de execução do n8n |
| Supervisor (LLM do n8n) falha | `onError: continueRegularOutput` | O `If` usa a regra de reserva: remediar se a categoria for `Acessos/Senhas` ou `Redes/VPN`. O Agente 2 recebe `action_type=AUTO_DETECT` e aplica a **própria política determinística**. | Fluxo continua; `supervisor_decision = {fallback: true}` |
| Agente 2: LLM do resumo falha | interno ao Agente 2 | Ações já executadas; resumo por template (`summary_source="template"`) | Resultado normal |
| Discord indisponível | `onError` no nó do Discord | Alerta gravado com `notified_channel=discord_FALHOU` | — |

**Teste real (RT-06):** Agente 2 parado → ticket `TCK-20261122-154852-305` com `error="connect ECONNREFUSED 172.17.0.1:8002"` → alerta `ALR-MWS6XVY1` com `agent=agent2`. Ver [`tests/REGRESSION_TESTS.md`](../tests/REGRESSION_TESTS.md).

## 3. Variáveis e secrets (configuração separada do código)

| Tipo | Onde fica | Itens | Por quê |
| :--- | :--- | :--- | :--- |
| **Segredos** | **Credenciais n8n** (criptografadas com `N8N_ENCRYPTION_KEY`; o JSON exportado só guarda **id e nome**) | `Helpdesk Agent 1 - X-API-Key` e `Helpdesk Agent 2 - X-API-Key` (Header Auth) · `Helpdesk Alertas - Discord Webhook` · `OpenAI account` (chave do proxy) | Nunca aparecem no workflow exportado nem no git |
| **Configuração** | Data Table **`helpdesk_config`** (key/value), lida no início de cada execução por `Carregar Configuracao` → `Montar Configuracao` | `AGENT1_BASE_URL=http://local:8001`, `AGENT2_BASE_URL=http://local:8002`, `POLL_INTERVAL_SECONDS=3`, `POLL_MAX_ATTEMPTS=40`, `HTTP_TIMEOUT_MS=15000`, `ALERT_CHANNEL=discord` | Trocar URL ou limite **sem editar nem republicar** o workflow. A edição Community não tem o recurso *Variables* (`$vars`), que é exclusivo do plano Enterprise. A Data Table cumpre o mesmo papel. |
| **Agentes** | `.env` da raiz (fora do git) · modelo em `.env.example` | `OPENAI_API_KEY`, `AGENT1_API_TOKEN`, `AGENT2_API_TOKEN`, `EMBEDDING_MODEL`, timeouts | O mesmo token vive no `.env` (lado do agente) e na credencial n8n (lado do cliente) |

Rotação de token:
1. Gere um novo valor: `python -c "import secrets;print(secrets.token_urlsafe(32))"`.
2. Atualize o `.env` e reinicie o agente.
3. Atualize a credencial no n8n (*Credentials → Helpdesk Agent N - X-API-Key*).

Nenhum workflow precisa ser alterado.

## 4. Como importar (instância nova)

1. Crie as Data Tables:
   - `helpdesk_tickets` (`ticket_id, status, stage, session_id, user_prompt, result_json, error_message, created_at, completed_at`);
   - `helpdesk_alerts` (colunas da seção 2);
   - `helpdesk_config` (`key, value, description`) com as linhas da seção 3.
2. Crie as credenciais:
   - Header Auth ×2: nome do header `X-API-Key`, valor igual ao do `.env`;
   - Discord Webhook: URL do canal;
   - OpenAI: Base URL `http://local:20128/v1`.
3. Importe e publique, nesta ordem: o sub-workflow de SLA, o Error Handler e depois o principal.
4. No principal, confira os IDs das Data Tables, do sub-workflow e do `errorWorkflow` (*Settings → Error workflow*).
