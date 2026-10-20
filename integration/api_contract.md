# Contrato de Integracao e Especificacao de APIs REST (TP3)

Este documento especifica o contrato oficial de comunicacao HTTP/REST dos dois agentes desenvolvidos no TP3 (**Agent 1: Triagem de TI N1** e **Agent 2: Auto-Remediacao e Despacho N2**), os schemas Pydantic v2 associados, o ciclo de vida dos estados assincronos e o modelo arquitetural de orquestracao desacoplada via **n8n** para o TP4.

---

## 1. Visao Geral dos Servicos e Portas

Ambos os microservicos sao implementados sobre **FastAPI** e operam de maneira 100% independente em portas distintas:

| Servico | Porta Local | Responsabilidade Tecnica | Modulo Principal |
| :--- | :---: | :--- | :--- |
| **Agent 1 (Triage)** | `8001` | Triagem inicial, classificacao de severidade, inferencia de categoria, CoT e decisao de escalonamento. | `agent1/app.py` |
| **Agent 2 (Remediation)** | `8002` | Execucao tecnica de acoes corretivas (Active Directory, VPN) e despacho formal de chamados com SLA. | `agent2/app.py` |

---

## 2. Contrato de API - Agent 1: Triagem de TI N1 (Porta 8001)

### 2.1 Endpoint: `POST /run`
- **Metodo:** `POST`
- **URL:** `http://localhost:8001/run`
- **Status de Resposta:** `202 Accepted`
- **Headers:** `Content-Type: application/json`

#### Schema de Entrada (`RunRequest` - Pydantic):
```json
{
  "type": "object",
  "required": ["user_prompt"],
  "properties": {
    "user_prompt": {
      "type": "string",
      "description": "Texto em linguagem natural contendo a descricao do chamado pelo usuario.",
      "example": "Nao consigo acessar a folha de pagamento. Erro 403. E-mail maria.souza@empresa.com. Urgente ate 17h."
    },
    "session_id": {
      "type": "string",
      "default": "default_session",
      "description": "Identificador da sessao para manutencao da memoria SQLite.",
      "example": "session_corp_maria_01"
    }
  }
}
```

#### Schema de Saida Imediata (`TaskInitiatedResponse`):
```json
{
  "task_id": "task_4f8a12e39b7c",
  "status": "pending",
  "message": "Chamado recebido com sucesso. Processamento de triagem iniciado em background."
}
```

---

### 2.2 Endpoint: `GET /status/{task_id}`
- **Metodo:** `GET`
- **URL:** `http://localhost:8001/status/{task_id}`
- **Status de Resposta:** `200 OK` (ou `404 Not Found` caso o ID nao exista)

#### Estados Possiveis da Tarefa:
- `pending`: A tarefa esta em execucao pelo runner assincrono (BackgroundTasks).
- `done`: Execucao finalizada com sucesso. Campo `result` contem o payload tipado.
- `error`: Falha durante o processamento. Campo `error` contem detalhes da excecao.

#### Schema de Saida Concluida (`TaskStatusResponse` com `HelpdeskResponse`):
```json
{
  "task_id": "task_4f8a12e39b7c",
  "status": "done",
  "created_at": "2026-10-19T14:10:00Z",
  "completed_at": "2026-10-19T14:10:02Z",
  "result": {
    "ticket_summary": "Erro de acesso 403 por bloqueio de conta no AD",
    "category": "Acessos/Senhas",
    "severity": "Alta",
    "recommended_action": "Solicitar desbloqueio da conta maria.souza@empresa.com no Active Directory e validar pertenca ao grupo Folha_Pagamento_Admin.",
    "requires_human_escalation": true,
    "reasoning_steps": [
      "Identificado sintoma de erro 403 e urgencia operacional (prazo de fechamento as 17h).",
      "Ferramenta check_system_status consultada: servico de folha operacional sem degradacao.",
      "Ferramenta lookup_user_account retornou account_locked=True para o e-mail da colaboradora.",
      "Artigo procedural KB-101 indica que conta bloqueada exige intervencao de suporte N2."
    ],
    "tools_invoked": [
      "check_system_status",
      "lookup_user_account",
      "query_troubleshooting_kb"
    ],
    "confidence_score": 0.98
  },
  "error": null
}
```

---

## 3. Contrato de API - Agent 2: Auto-Remediacao e Despacho N2 (Porta 8002)

### 3.1 Endpoint: `POST /run`
- **Metodo:** `POST`
- **URL:** `http://localhost:8002/run`
- **Status de Resposta:** `202 Accepted`
- **Headers:** `Content-Type: application/json`

#### Schema de Entrada (`RemediationRequest` - Pydantic):
```json
{
  "type": "object",
  "required": ["ticket_id", "user_email", "category", "severity", "recommended_action"],
  "properties": {
    "ticket_id": {
      "type": "string",
      "description": "Identificador unico do chamado triado.",
      "example": "TCK-40301-BR"
    },
    "user_email": {
      "type": "string",
      "description": "E-mail corporativo do colaborador alvo da acao.",
      "example": "maria.souza@empresa.com"
    },
    "category": {
      "type": "string",
      "description": "Categoria determinada na triagem.",
      "example": "Acessos/Senhas"
    },
    "severity": {
      "type": "string",
      "description": "Nivel de severidade do chamado (Baixa, Media, Alta, Critica).",
      "example": "Alta"
    },
    "recommended_action": {
      "type": "string",
      "description": "Descricao da acao tecnica a ser executada.",
      "example": "Solicitar desbloqueio da conta no Active Directory para liberacao da folha."
    },
    "requires_human_escalation": {
      "type": "boolean",
      "default": false,
      "description": "Indica se requer despacho complementar para plantonista N2."
    },
    "action_type": {
      "type": "string",
      "enum": ["UNLOCK_ACCOUNT", "VPN_FAILOVER", "DISPATCH_INCIDENT", "AUTO_DETECT"],
      "default": "AUTO_DETECT"
    }
  }
}
```

#### Schema de Saida Imediata (`TaskInitiatedResponse`):
```json
{
  "task_id": "rem_task_9c8b7a6f5e4d",
  "status": "pending",
  "message": "Operacao de remediacao registrada com sucesso. Execucao iniciada em background."
}
```

---

### 3.2 Endpoint: `GET /status/{task_id}`
- **Metodo:** `GET`
- **URL:** `http://localhost:8002/status/{task_id}`
- **Status de Resposta:** `200 OK` (ou `404 Not Found`)

#### Schema de Saida Concluida (`TaskStatusResponse` com `RemediationResponse`):
```json
{
  "task_id": "rem_task_9c8b7a6f5e4d",
  "status": "done",
  "created_at": "2026-10-19T14:12:00Z",
  "completed_at": "2026-10-19T14:12:01Z",
  "result": {
    "remediation_id": "REM-7B91C2D4",
    "ticket_id": "TCK-40301-BR",
    "status": "SUCCESS",
    "actions_executed": [
      {
        "action_name": "unlock_user_account",
        "target": "maria.souza@empresa.com",
        "status": "SUCCESS",
        "message": "Conta de Maria Souza desbloqueada com sucesso no Active Directory.",
        "timestamp": "2026-10-19T14:12:01Z"
      }
    ],
    "sla_target_minutes": 15,
    "audit_trail": [
      "AD_UNLOCK: AUDIT-AD-4E82F1 - maria.souza@empresa.com"
    ],
    "resolution_summary": "Conta corporativa maria.souza@empresa.com desbloqueada e ativa no Active Directory.",
    "escalation_team": null
  },
  "error": null
}
```

---

## 4. Orquestracao Deterministica no n8n para o TP4 (Sem Chamadas Diretas)

### 4.1 Principio do Desacoplamento Absoluto
O **Agent 1** e o **Agent 2** foram concebidos como projetos e microservicos totalmente desacoplados:
- O código do Agent 1 **não importa, não conhece e não chama** o Agent 2.
- O código do Agent 2 **não importa, não conhece e não chama** o Agent 1.
- Nenhum dos agentes compartilha banco de dados relacional (`agent1_sessions.db` é exclusivo do Agent 1).

### 4.2 Arquitetura do Workflow no n8n (TP4):

```
       [Gatilho do Usuário / Webhook n8n]
                       │
                       ▼
        [HTTP POST http://localhost:8001/run] (Agent 1 - Triagem N1)
                       │ (Recebe 202 com task_id)
                       ▼
      [HTTP GET http://localhost:8001/status/{task_id}] (Polling)
                       │
                       ▼
            [n8n Conditional Switch]
           /                         \
  (Auto-Remediável / AD / VPN)     (Sem Ação Automática)
          │                                  │
          ▼                                  ▼
[HTTP POST http://localhost:8002/run]      [Notifica Colaborador]
       (Agent 2 - Remediação)
          │ (Recebe 202 com rem_task_id)
          ▼
[HTTP GET http://localhost:8002/status/{rem_task_id}]
          │
          ▼
[Gera Relatório de Atendimento & Envia Slack / E-mail]
```

### 4.3 Vantagens da Abordagem Mediada pelo n8n:
1. **Seguranca e Governanca:** Nenhuma alteracao no Active Directory pode ocorrer sem que o orquestrador valide a saida da triagem e registre o log de auditoria.
2. **Escalabilidade Independente:** Se a demanda de triagem for 10x maior que a de remediadores de conta, o Agent 1 pode ser escalado horizontalmente sem impactar o Agent 2.
3. **Resiliencia e Retry:** Caso a chamada ao Agent 2 sofra um erro transitorio de rede, o proprio n8n gerencia politicas de retentativa com backoff exponencial, sem travar a thread de triagem do Agent 1.
