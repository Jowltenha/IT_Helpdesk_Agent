# AGENTS.md - Catálogo e Contrato Formal do Agente 1 (Triagem N1)

## 📌 Identificação do Agente
- **Nome Oficial:** `IT_Helpdesk_N1_Agent`
- **Papel:** Agente de Triagem Inicial e Diagnóstico de Chamados Corporativos (Nível 1)
- **Porta do Serviço:** `8001` (FastAPI)
- **Framework de Execução:** OpenAI Agents SDK (`from agents import Agent, Runner`)
- **Modelo de Linguagem:** `ag/claude-sonnet-4-6`

---

## 📥 Contrato de Entrada (Input Contract)
- **Endpoint:** `POST /run`
- **Schema Pydantic:** `RunRequest`
  ```json
  {
    "user_prompt": "string (relato em linguagem natural do problema técnico)",
    "session_id": "string (identificador único da sessão para memória multi-turnos)"
  }
  ```

---

## 📤 Contrato de Saída (Output Contract)
- **Endpoint:** `GET /status/{task_id}`
- **Schema Pydantic:** `HelpdeskResponse` (estritamente tipado, sem formatação markdown)
  ```json
  {
    "ticket_summary": "string (resumo em até 10 palavras)",
    "category": "string (Hardware | Software | Redes/VPN | Acessos/Senhas | Outros)",
    "severity": "string (Baixa | Media | Alta | Critica)",
    "recommended_action": "string (instruções acionáveis de resolução)",
    "requires_human_escalation": "boolean (se exige intervenção presencial/humana)",
    "reasoning_steps": ["string (4 etapas do raciocínio Chain-of-Thought)"],
    "tools_invoked": ["string (nomes das ferramentas Python acionadas)"],
    "confidence_score": "float (0.0 a 1.0)"
  }
  ```

---

## 🛠️ Catálogo de Ferramentas e Hooks

### Ferramentas (@function_tool):
1. `check_system_status`: Monitoria operacional de serviços (`vpn`, `folha`, `email`, `erp`).
2. `lookup_user_account`: Consulta perfil e bloqueio no Active Directory (`account_locked`).
3. `query_troubleshooting_kb`: Recuperação de artigos procedurais SOP.

### Hooks Automatizados:
- **`PreToolUse` (`hooks/pre_tool_validator.py`):** Intercepta e valida os argumentos das tools antes da execução física, bloqueando tentativas de injeção e e-mails fora do domínio `@empresa.com`.

---

## 🧩 Subagentes Vinculados
- **`kb-researcher` (`subagents/kb_researcher.md`):** Subagente especialista com isolamento de contexto dedicado para pesquisa semântica de SOPs e síntese de procedimentos sem poluição da janela de contexto principal.

---

## 🔒 Políticas de Segurança (`settings.json`)
- **Regras `allow`:** Execução de testes de API e leitura de logs.
- **Regras `deny`:** Comandos destrutivos no disco e exclusão do banco de sessões.
- **Regras `ask`:** Alterações em schemas de dados e reinicialização de serviços de rede.
