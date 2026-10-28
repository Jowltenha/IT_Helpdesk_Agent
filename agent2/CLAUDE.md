# CLAUDE.md - Agent 2: Agente de Auto-Remediacao e Despacho de TI N2

## 📌 Context Engineering Strategy: Inverted Pyramid & Guardrail Constraints
Este arquivo aplica a estrategia de **Inverted Pyramid (Piramide Invertida) combinada com Guardrail Constraints (Restricoes Críticas Ancoradas)**. A informacao e disposta do mais urgente e operacional para os detalhes de implementacao:
1. **Top-Level Directives (Diretrizes Operacionais Criticas):** O que deve ser executado de imediato, regras de seguranca e limites de acao.
2. **API & Endpoints Contract (Contrato HTTP):** Especificacao dos endpoints REST `POST /run` e `GET /status/{task_id}` na porta 8002.
3. **Tool Execution Protocol (Catalogo de Ferramentas):** Regras de invocacao das funcoes de desbloqueio, VPN e ITSM.
4. **Pydantic Schemas & Architecture (Estrutura e Tipagem):** Modelos de dados e hierarquia de arquivos do projeto.

---

## 🎯 1. Top-Level Directives (Diretrizes Operacionais Críticas)

O **Agent 2** e um microservico autonomo especializado em **Resolucao Tecnica Automatizada e Despacho de Incidentes N2/N3**.
- **Missao Exclusiva:**
  - Receber diretrizes de chamados ja triados (com e-mail do colaborador, categoria, severidade e acao recomendada).
  - Executar acoes diretas no ambiente atraves de ferramentas Python:
    1. Desbloqueio imediato de contas corporativas bloqueadas por tentativas incorretas (`unlock_user_account`).
    2. Provisionamento de rotas de failover para usuarios em gateways de VPN instaveis (`configure_vpn_failover_route`).
    3. Criacao e despacho de incidentes no sistema ITSM com calculo rigoroso de SLA operacional (`dispatch_sla_incident`).
  - Gerar trilha de auditoria completa (`audit_trail`) e saida tipada com `RemediationResponse`.
- **Restricoes Criticas e Guardrails:**
  - O Agent 2 **NUNCA** executa triagem de linguagem natural bruta; ele exige dados de entrada estruturados via `RemediationRequest`.
  - O Agent 2 **NAO** chama e nem se comunica com o Agent 1. A orquestracao e passagem de contexto e feita pelo **n8n**.
  - Todas as acoes devem emitir codigo de rastreabilidade (ex: `AUDIT-AD-XXXX`, `VPN-FAILOVER-XXXX`, `INC-YYYYMM-XXXX`).

---

## 🌐 2. API & Endpoints Contract (Porta 8002)

O Agent 2 roda de forma independente na porta **8002** via FastAPI:

### 1. `POST /run`
- **Descricao:** Registra o pedido de remediacao/despacho e dispara o processamento assincrono via `BackgroundTasks`.
- **Status HTTP:** `202 Accepted`
- **Headers:** `Content-Type: application/json`
- **Payload de Entrada (`RemediationRequest`):**
  ```json
  {
    "ticket_id": "TCK-40301-BR",
    "user_email": "maria.souza@empresa.com",
    "category": "Acessos/Senhas",
    "severity": "Alta",
    "recommended_action": "Solicitar desbloqueio da conta no Active Directory para liberacao do sistema de folha de pagamento.",
    "requires_human_escalation": false,
    "action_type": "UNLOCK_ACCOUNT"
  }
  ```
- **Resposta Imediata (`TaskInitiatedResponse`):**
  ```json
  {
    "task_id": "rem_task_1a2b3c4d5e6f",
    "status": "pending",
    "message": "Operacao de remediacao registrada com sucesso. Execucao iniciada em background."
  }
  ```

### 2. `GET /status/{task_id}`
- **Descricao:** Permite consultar o andamento e o relatorio final da remediacao.
- **Estados Possiveis:** `pending`, `done`, `error`.
- **Resposta Concluida (`TaskStatusResponse`):**
  ```json
  {
    "task_id": "rem_task_1a2b3c4d5e6f",
    "status": "done",
    "created_at": "2026-10-19T14:02:00Z",
    "completed_at": "2026-10-19T14:02:01Z",
    "result": {
      "remediation_id": "REM-4A82F19E",
      "ticket_id": "TCK-40301-BR",
      "status": "SUCCESS",
      "actions_executed": [
        {
          "action_name": "unlock_user_account",
          "target": "maria.souza@empresa.com",
          "status": "SUCCESS",
          "message": "Conta de Maria Souza desbloqueada com sucesso no Active Directory.",
          "timestamp": "2026-10-19T14:02:01Z"
        }
      ],
      "sla_target_minutes": 15,
      "audit_trail": [
        "AD_UNLOCK: AUDIT-AD-7B91C2 - maria.souza@empresa.com"
      ],
      "resolution_summary": "Conta corporativa maria.souza@empresa.com desbloqueada e ativa no Active Directory.",
      "escalation_team": null
    },
    "error": null
  }
  ```

### 3. `GET /health`
- Retorna `{"status": "ok", "agent": "Agent 2 - Remediation & ITSM Dispatcher", "version": "1.0.0"}`.

---

## 🛠️ 3. Tool Execution Protocol (Catalogo de Ferramentas)

- `unlock_user_account(user_email: str, reason: str) -> str`:
  - Altera o estado do usuario no Active Directory (`account_locked = False`), zera falhas consecutivas e gera codigo de auditoria.
- `configure_vpn_failover_route(user_email: str, gateway: str) -> str`:
  - Configura rota estatica para o gateway redundante `BR-SA-02` e gera token de sessao de contingencia.
- `dispatch_sla_incident(ticket_id: str, severity: str, team: str, justification: str) -> str`:
  - Cria registro no sistema ITSM corporativo e calcula a meta de atendimento:
    - *Critica:* 30 minutos
    - *Alta:* 120 minutos
    - *Media:* 480 minutos
    - *Baixa:* 1440 minutos

---

## 📁 4. Pydantic Schemas & Arquitetura de Arquivos

```
agent2/
├── app.py              # FastAPI: endpoints POST /run, GET /status/{task_id}, GET /health (Porta 8002)
├── runner.py           # RemediationAgentRunner: logica de intervencao, auditoria e sintese
├── models.py           # Schemas Pydantic v2: RemediationRequest, RemediationResponse, TaskStatus
├── tools.py            # Ferramentas Python (@function_tool): unlock_user, vpn_failover, dispatch_sla
├── test_agent2_api.py  # Suite de testes HTTP automatizados
└── CLAUDE.md           # Contrato de contexto e diretrizes tecnicas do Agent 2
```

---

## 💡 Decisoes Tecnicas de Engenharia

1. **Desacoplamento e Porta Dedicada (8002):**
   - Roda em porta distinta do Agent 1 (8001), permitindo que ambos os servicos fiquem ativos simultaneamente no ambiente Antigravity sem colisao de sockets.
2. **Trilha de Auditoria Estrita (`audit_trail`):**
   - Toda alteracao de seguranca (desbloqueio de credenciais e rotas de rede) gera um identificador imutavel gravado no payload de resposta para fins de compliance SOX/LGPD.
3. **FastAPI BackgroundTasks para Nao-Bloqueio:**
   - Mantem paridade arquitetural com o Agent 1, permitindo que orquestradores (n8n) recebam `202 Accepted` imediatamente e monitorem o progresso via polling em `/status/{task_id}`.
