# AGENTS.md - Catálogo e Contrato Formal do Agente 2 (Auto-Remediação N2)

## 📌 Identificação do Agente
- **Nome Oficial:** `IT_Remediation_N2_Agent`
- **Papel:** Agente de Auto-Remediação e Despacho de Incidentes (Nível 2 / ITSM)
- **Porta do Serviço:** `8002` (FastAPI)
- **Framework de Execução:** FastAPI com processamento assíncrono em `BackgroundTasks`
- **Modelo de Linguagem:** `ag/claude-sonnet-4-6`

---

## 📥 Contrato de Entrada (Input Contract)
- **Endpoint:** `POST /run`
- **Schema Pydantic:** `RemediationRequest`
  ```json
  {
    "ticket_id": "string (código do chamado original triado)",
    "user_email": "string (e-mail do colaborador afetado)",
    "category": "string (Acessos/Senhas | Redes/VPN | Hardware | Outros)",
    "severity": "string (Baixa | Media | Alta | Critica)",
    "recommended_action": "string (ação recomendada pela triagem N1)",
    "requires_human_escalation": "boolean (se exige abertura de chamado formal no ITSM)",
    "action_type": "string (opcional: UNLOCK_ACCOUNT | VPN_FAILOVER | ESCALATE_ONLY)"
  }
  ```

---

## 📤 Contrato de Saída (Output Contract)
- **Endpoint:** `GET /status/{task_id}`
- **Schema Pydantic:** `RemediationResponse`
  ```json
  {
    "remediation_id": "string (identificador da intervenção REM-XXXXXXXX)",
    "ticket_id": "string (código do chamado original)",
    "status": "string (SUCCESS | PARTIAL | ESCALATED)",
    "actions_executed": [
      {
        "action_name": "string",
        "target": "string",
        "status": "string",
        "message": "string",
        "timestamp": "string (ISO 8601)"
      }
    ],
    "sla_target_minutes": "integer (meta de atendimento: 15, 30, 120, 480, 1440)",
    "audit_trail": ["string (códigos e tokens de auditoria gerados)"],
    "resolution_summary": "string (resumo executivo da remediação)",
    "escalation_team": "string ou null (equipe N2/N3 acionada)"
  }
  ```

---

## 🛠️ Catálogo de Ferramentas e Hooks

### Ferramentas de Remediação:
1. `unlock_user_account`: Executa o desbloqueio da conta no Active Directory e zera falhas consecutivas.
2. `configure_vpn_failover_route`: Provisiona gateway de contingência (`BR-SA-02`) e token de sessão redundante.
3. `dispatch_sla_incident`: Cadastra incidente no sistema ITSM com cálculo de tempo de resposta por severidade.

### Hook Automatizado de Segurança:
- **`PostToolUse` (`hooks/post_tool_auditor.py`):** Intercepta os retornos das ferramentas, gera um hash criptográfico SHA-256 (`compliance_hash: SEC-XXXX`) e grava o evento em `hooks/security_audit.log`.

---

## 🧩 Subagentes Vinculados
- **`sla-compliance-auditor` (`subagents/sla_auditor.md`):** Subagente especialista com isolamento de contexto para computação de metas de SLA e conformidade de despacho ITSM sem interferência de execuções de rede.

---

## 🔒 Políticas de Segurança (`settings.json`)
- **Regras `allow`:** Execução de testes de API e leitura de logs de segurança.
- **Regras `deny`:** Remoção de logs de auditoria (`execution_log.json`, `security_audit.log`) e comandos destrutivos no sistema operacional.
- **Regras `ask`:** Operações de remediação em lote ou despacho de incidentes para diretoria executiva.
