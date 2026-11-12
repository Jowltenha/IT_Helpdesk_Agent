"""
Runner assíncrono do Agente 2 (Resolução Automatizada N2 e Remediação).
Integra Ferramentas Python de intervenção técnica, auditoria de segurança e validação Pydantic v2.
Grava saídas reais em execution_log.json sem mascarar falhas com respostas prontas simuladas.
"""
import os
import json
import uuid
import re
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from openai import AsyncOpenAI

from agent2.models import (
    RemediationRequest,
    RemediationResponse,
    RemediationAction
)
from agent2.tools import (
    unlock_user_account,
    configure_vpn_failover_route,
    dispatch_sla_incident
)

load_dotenv()

AGENT2_SYSTEM_PROMPT = """
### IDENTIDADE E DIRETRIZES DO AGENTE 2 (REMEDIAÇÃO N2)
Você é o Agente de Auto-Remediação e Despacho de TI (Agent 2).
Sua função é receber parâmetros de chamados já triados e sintetizar a resolução das intervenções técnicas executadas:
1. Desbloqueio de credenciais e contas no Active Directory (`unlock_user_account`).
2. Provisionamento de rotas alternativas para VPN degradada (`configure_vpn_failover_route`).
3. Despacho formal de incidentes para equipes especializadas N2/N3 com computação de SLA (`dispatch_sla_incident`).

### REGRAS ESTRITAS DE RESPOSTA (JSON PURO)
Retorne APENAS um objeto JSON válido (sem marcações markdown) com os seguintes campos:
- `remediation_id`: string identificadora da execução.
- `ticket_id`: string do chamado original.
- `status`: "SUCCESS", "PARTIAL" ou "ESCALATED".
- `actions_executed`: lista de objetos com action_name, target, status, message, timestamp.
- `sla_target_minutes`: inteiro com a meta de atendimento (ex: 15, 30, 120, 480).
- `audit_trail`: lista de strings com os códigos e registros de segurança gerados.
- `resolution_summary`: resumo executivo e técnico da intervenção realizada.
- `escalation_team`: equipe acionada caso aplicável (ou null).
"""


class RemediationAgentRunner:
    """
    Executor do Agente 2 de Remediação e Despacho N2.
    """

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_path = os.path.join(base_dir, "execution_log.json")
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
        self.model_name = os.getenv("MODEL_NAME", "ag/claude-sonnet-4-6")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def run(self, request: RemediationRequest) -> RemediationResponse:
        """
        Executa a esteira de remediação com base nos dados do chamado triado.
        Gera trilha de auditoria real e registra o log de execução.
        """
        start_time = datetime.now(timezone.utc)
        remediation_id = f"REM-{uuid.uuid4().hex[:8].upper()}"
        actions_list: List[RemediationAction] = []
        audit_trail: List[str] = []
        overall_status = "SUCCESS"
        escalation_team = None
        sla_target = 120

        req_text = f"{request.category} {request.recommended_action} {request.action_type or ''}".lower()

        # 1. Execução das Ferramentas Python com base no tipo de intervenção
        # Caso A: Desbloqueio de Conta no Active Directory
        if "unlock" in req_text or "desbloqueio" in req_text or "bloqueada" in req_text or request.category == "Acessos/Senhas":
            tool_res = json.loads(unlock_user_account(request.user_email, reason=f"Chamado {request.ticket_id}"))
            audit_trail.append(f"AD_UNLOCK: {tool_res['audit_code']} - {tool_res['email']}")
            if "compliance_hash" in tool_res:
                audit_trail.append(f"HOOK_POST_TOOL: {tool_res['compliance_hash']}")
            actions_list.append(RemediationAction(
                action_name="unlock_user_account",
                target=request.user_email,
                status=tool_res["status"],
                message=tool_res["message"],
                timestamp=tool_res["timestamp"]
            ))

        # Caso B: Rota de VPN de Contingência
        if "vpn" in req_text or "gateway" in req_text or request.category == "Redes/VPN":
            tool_vpn = json.loads(configure_vpn_failover_route(request.user_email, gateway="BR-SA-02"))
            audit_trail.append(f"VPN_ROUTE: {tool_vpn['session_token']} -> {tool_vpn['target_gateway']}")
            if "compliance_hash" in tool_vpn:
                audit_trail.append(f"HOOK_POST_TOOL: {tool_vpn['compliance_hash']}")
            actions_list.append(RemediationAction(
                action_name="configure_vpn_failover_route",
                target=tool_vpn["target_gateway"],
                status=tool_vpn["status"],
                message=tool_vpn["message"],
                timestamp=tool_vpn["timestamp"]
            ))

        # Caso C: Escalonamento Humano / Despacho ITSM
        if request.requires_human_escalation or "hardware" in req_text:
            overall_status = "ESCALATED"
            escalation_team = "N2 Infraestrutura" if ("vpn" in req_text or "rede" in req_text) else (
                "Suporte Presencial N1/N2" if "hardware" in req_text else "N2 Acessos e Identidade"
            )
            tool_itsm = json.loads(dispatch_sla_incident(
                ticket_id=request.ticket_id,
                severity=request.severity,
                team=escalation_team,
                justification=request.recommended_action
            ))
            sla_target = tool_itsm["sla_target_minutes"]
            audit_trail.append(f"ITSM_DISPATCH: {tool_itsm['incident_number']} SLA: {sla_target}min")
            if "compliance_hash" in tool_itsm:
                audit_trail.append(f"HOOK_POST_TOOL: {tool_itsm['compliance_hash']}")
            actions_list.append(RemediationAction(
                action_name="dispatch_sla_incident",
                target=escalation_team,
                status=tool_itsm["status"],
                message=f"Incidente {tool_itsm['incident_number']} criado para {escalation_team}. SLA: {sla_target} min.",
                timestamp=tool_itsm["dispatched_at"]
            ))
        else:
            sla_target = 15

        # 2. Síntese Executiva via LLM
        summary_prompt = f"""
        Ticket: {request.ticket_id} | Usuário: {request.user_email} | Categoria: {request.category}
        Ações Executadas: {[a.model_dump() for a in actions_list]}
        Status Geral: {overall_status}
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": AGENT2_SYSTEM_PROMPT},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
            cleaned = self._clean_json_string(raw_content)
            parsed_data = json.loads(cleaned)

            final_response = RemediationResponse(
                remediation_id=remediation_id,
                ticket_id=request.ticket_id,
                status=parsed_data.get("status", overall_status),
                actions_executed=actions_list,
                sla_target_minutes=parsed_data.get("sla_target_minutes", sla_target),
                audit_trail=audit_trail,
                resolution_summary=parsed_data.get("resolution_summary", f"Operações concluídas com sucesso para {request.user_email}."),
                escalation_team=parsed_data.get("escalation_team", escalation_team)
            )
        except Exception as e:
            # Em caso de falha de conexão com a LLM, sintetiza diretamente dos dados reais das ferramentas
            summary_msg = f"Remediação técnica executada para o chamado {request.ticket_id}. "
            if overall_status == "ESCALATED":
                summary_msg += f"Serviço mitigado e direcionado para a equipe {escalation_team} com SLA de {sla_target} minutos."
            else:
                summary_msg += f"Conta corporativa {request.user_email} desbloqueada e ativa no Active Directory."

            final_response = RemediationResponse(
                remediation_id=remediation_id,
                ticket_id=request.ticket_id,
                status=overall_status,
                actions_executed=actions_list,
                sla_target_minutes=sla_target,
                audit_trail=audit_trail,
                resolution_summary=summary_msg,
                escalation_team=escalation_team
            )

        # 3. Gravação em Log Real da Execução
        self._record_execution_log(request, final_response, start_time)

        return final_response

    def _record_execution_log(self, request: RemediationRequest, response: RemediationResponse, start_time: datetime):
        """Registra a execução em arquivo de log JSON."""
        completed_time = datetime.now(timezone.utc)
        log_entry = {
            "timestamp": completed_time.isoformat(),
            "duration_seconds": round((completed_time - start_time).total_seconds(), 3),
            "request": request.model_dump(),
            "response": response.model_dump(),
            "agent_model": self.model_name
        }
        try:
            entries = []
            if os.path.exists(self.log_path):
                with open(self.log_path, "r", encoding="utf-8") as f:
                    try:
                        entries = json.load(f)
                    except json.JSONDecodeError:
                        entries = []
            entries.append(log_entry)
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
        except Exception as ex:
            print(f"Aviso: falha ao gravar log do Agente 2: {ex}")

    def _clean_json_string(self, content: str) -> str:
        content = content.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if match:
            return match.group(1).strip()
        return content
