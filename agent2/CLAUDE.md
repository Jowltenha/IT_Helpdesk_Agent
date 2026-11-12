# CLAUDE.md - Agent 2: Agente de Auto-Remediação e Despacho N2 (TP4)

## 📌 Context Engineering Strategy: Inverted Pyramid & Formal Governance
Este arquivo aplica a estratégia de **Inverted Pyramid (Pirâmide Invertida) combinada com Formal Governance & Guardrails**. A informação é disposta do mais urgente e operacional para as especificações técnicas, servindo como a **fonte única da verdade** do **Agente 2**:
1. **Top-Level Directives (Diretrizes Operacionais Críticas):** Ações imediatas, limites de atuação e regras de segurança.
2. **API & Endpoints Contract (Contrato HTTP Assíncrono):** Especificação dos endpoints REST `POST /run` e `GET /status/{task_id}` na porta 8002.
3. **Tool Execution Protocol & Hooks (Ferramentas e PostToolUse):** Invocação de remediação e injeção de compliance criptográfico SHA-256.
4. **Skills, Subagentes e Permissões (Especificação Formal TP4):** Regras do `settings.json`, skill `SKILL.md` e subagente `sla-compliance-auditor`.
5. **Mapeamento de Requisitos e Rastreabilidade:** Tabela comparativa entre os requisitos do projeto e as entregas implementadas.

---

## 🎯 1. Top-Level Directives (Diretrizes Operacionais Críticas)

O **Agent 2** é um microserviço autônomo especializado em **Resolução Técnica Automatizada e Despacho de Incidentes N2/N3**.
- **Missão Exclusiva:**
  - Receber chamados já previamente triados pelo Agente 1 (via n8n) em formato JSON estruturado (`RemediationRequest`).
  - Executar ações diretas no ambiente através de ferramentas Python:
    1. Desbloqueio imediato de contas corporativas no Active Directory (`unlock_user_account`).
    2. Provisionamento de rotas de failover para usuários em gateways de VPN instáveis (`configure_vpn_failover_route`).
    3. Criação e despacho de incidentes no sistema ITSM com cálculo rigoroso de SLA operacional (`dispatch_sla_incident`).
  - Interceptar cada execução com o hook `PostToolUse` (`hooks/post_tool_auditor.py`) para gerar hash criptográfico imutável (`compliance_hash: SEC-XXXX`).
  - Gerar trilha de auditoria completa (`audit_trail`) e saída tipada com `RemediationResponse`.
- **Restrições Críticas e Guardrails:**
  - O Agent 2 **NUNCA** processa linguagem natural bruta; ele exige dados de entrada estruturados via `RemediationRequest`.
  - O Agent 2 **NÃO** chama e nem se comunica diretamente com o Agent 1. Toda a orquestração é mediada pelo **n8n**.
  - Todas as ações emitem código de rastreabilidade único (ex: `AUDIT-AD-XXXX`, `VPN-FAILOVER-XXXX`, `INC-YYYYMM-XXXX`).

---

## 📁 2. Estrutura e Hierarquia de Arquivos do Agente 2

```
agent2/
├── app.py                      # FastAPI: endpoints assíncronos POST /run, GET /status/{task_id}, GET /health (Porta 8002)
├── runner.py                   # RemediationAgentRunner assíncrono com gravação real de logs
├── models.py                   # Modelos Pydantic v2: RemediationRequest, RemediationResponse, TaskStatus
├── tools.py                    # Ferramentas Python de remediação (@function_tool) com hook PostToolUse
├── settings.json               # Especificação formal de permissões (allow, deny, ask) e governança
├── SKILL.md                    # Skill reutilizável de Governança: sla-incident-dispatch
├── hooks/
│   ├── post_tool_auditor.py    # Hook PostToolUse: gera hash SHA-256 e injeta compliance em security_audit.log
│   ├── test_hook.py            # Testes automatizados do hook
│   └── security_audit.log      # Trilha de auditoria gerada pelo hook
├── subagents/
│   └── sla_auditor.md          # Subagente com isolamento de contexto para auditoria e governança de SLA
├── test_agent2_api.py          # Suíte de testes HTTP automatizados
├── execution_log.json          # Registro real de execuções (sem mocks pré-fabricados)
├── AGENTS.md                   # Catálogo formal de contratos do Agente 2
└── CLAUDE.md                   # Fonte única de verdade e diretrizes técnicas do Agente 2
```

---

## 🌐 3. API & Endpoints Contract (Porta 8002)

O Agent 2 roda de forma independente na porta **8002** via FastAPI:

### 1. `POST /run` (Status: `202 Accepted`)
- **Descrição:** Registra o pedido de remediação e inicia processamento em background sem travar o cliente HTTP.
- **Payload de Entrada (`RemediationRequest`):**
  ```json
  {
    "ticket_id": "TCK-40301-BR",
    "user_email": "maria.souza@empresa.com",
    "category": "Acessos/Senhas",
    "severity": "Alta",
    "recommended_action": "Solicitar desbloqueio da conta no Active Directory.",
    "requires_human_escalation": false,
    "action_type": "UNLOCK_ACCOUNT"
  }
  ```
- **Resposta Imediata (`TaskInitiatedResponse`):**
  ```json
  {
    "task_id": "rem_task_1a2b3c4d5e6f",
    "status": "pending",
    "message": "Operação de remediação registrada com sucesso. Execução iniciada em background."
  }
  ```

### 2. `GET /status/{task_id}`
- **Estados Possíveis:** `pending`, `done`, `error`.
- **Resposta Concluída (`TaskStatusResponse` contendo `RemediationResponse`):**
  ```json
  {
    "task_id": "rem_task_1a2b3c4d5e6f",
    "status": "done",
    "created_at": "2026-11-12T10:00:00Z",
    "completed_at": "2026-11-12T10:00:02Z",
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
          "timestamp": "2026-11-12T10:00:01Z"
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

---

## 🛠️ 4. Protocolo de Ferramentas e Hook `PostToolUse`

1. `unlock_user_account(user_email: str, reason: str) -> str`: Altera `account_locked = False`, zera tentativas inválidas e emite código de auditoria.
2. `configure_vpn_failover_route(user_email: str, gateway: str) -> str`: Roteia para o gateway de contingência `BR-SA-02` e emite token de sessão.
3. `dispatch_sla_incident(ticket_id: str, severity: str, team: str, justification: str) -> str`: Cadastra incidente no ITSM e computa a meta de SLA.
4. **Hook `PostToolUse` (`hooks/post_tool_auditor.py`):**
   - Intercepta os retornos das ferramentas de remediação.
   - Computa o hash de integridade SHA-256 (`compliance_hash: SEC-XXXX`).
   - Grava a trilha imutável no arquivo `hooks/security_audit.log`.

---

## 🛡️ 5. Governança, Permissões, Skill e Subagente

### 1. Políticas de Permissão (`settings.json`):
- **`allow`:** Execução de testes de API (`test_agent2_api.py`), testes de hook (`test_hook.py`) e leitura de logs.
- **`deny`:** Remoção de logs de auditoria (`rm execution_log.json`, `rm security_audit.log`) e comandos destrutivos no sistema.
- **`ask`:** Desbloqueio em massa de contas corporativas ou modificação de arquivos de endpoints da API.

### 2. Skill Reutilizável (`SKILL.md`):
- **Nome:** `sla-incident-dispatch`.
- Define a matriz corporativa de SLA e o procedimento de escalonamento técnico N2/N3.

### 3. Subagente Especialista (`subagents/sla_auditor.md`):
- **Nome:** `sla-compliance-auditor` | **Modelo:** `ag/claude-sonnet-4-6`.
- **Ferramentas:** `dispatch_sla_incident`.
- **Justificativa de Isolamento:** Separa a governança e conformidade SOX/LGPD das operações físicas de rede e credenciais, assegurando auditoria limpa e sem interferência de estados transitórios de execução técnica.

---

## 📊 6. Mapeamento de Requisitos e Rastreabilidade

| Requisito do Projeto | Componente / Implementação | Estado Atual no TP4 |
| :--- | :--- | :---: |
| **Dois Agentes Desacoplados** | `agent2/` independente do `agent1/` na porta 8002 | ✅ Concluído |
| **Auto-Remediação Automatizada** | Desbloqueio AD, rota VPN redundante e despacho SLA | ✅ Concluído |
| **API REST Assíncrona** | `POST /run` (202) e `GET /status/{task_id}` com BackgroundTasks | ✅ Concluído |
| **Especificação de Permissões** | `agent2/settings.json` com regras `allow`, `deny` e `ask` | ✅ Concluído |
| **Hook PostToolUse de Segurança** | `hooks/post_tool_auditor.py` com hash SHA-256 imutável | ✅ Concluído |
| **Skills Reutilizáveis** | `agent2/SKILL.md` (`sla-incident-dispatch`) | ✅ Concluído |
| **Subagentes com Isolamento** | `agent2/subagents/sla_auditor.md` com justificativa formal | ✅ Concluído |
| **Orquestração n8n e Sub-workflow** | Integrado via `Execute Workflow` e `Merge` no n8n | ✅ Concluído |
