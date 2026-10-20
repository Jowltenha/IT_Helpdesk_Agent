"""
Runner assincrono do Agente 2 (Resolucao Automatizada N2 e Remediacao).
Integra Ferramentas Python de intervencao, auditoria de seguranca e validacao Pydantic v2.
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
### IDENTIDADE E DIRETRIZES DO AGENTE 2 (REMEDIACAO N2)
Voce e o Agente de Auto-Remediacao e Despacho de TI (Agent 2).
Sua funcao e receber tickets tecnicos triados e executar procedimentos corretivos atraves de ferramentas especializadas:
1. Desbloqueio de credenciais e contas no Active Directory (`unlock_user_account`).
2. Provisionamento de rotas alternativas para VPN degradada (`configure_vpn_failover_route`).
3. Despacho formal de incidentes para equipes especializadas N2/N3 com computacao de SLA (`dispatch_sla_incident`).

### REGRAS ESTRITAS DE RESPOSTA
Retorne APENAS um objeto JSON valido (sem marcacoes markdown) com:
- `remediation_id`: string identificadora da execucao.
- `ticket_id`: string do chamado original.
- `status`: "SUCCESS", "PARTIAL" ou "ESCALATED".
- `actions_executed`: lista de objetos com action_name, target, status, message, timestamp.
- `sla_target_minutes`: inteiro com a meta de atendimento (ex: 30, 120, 480).
- `audit_trail`: lista de strings com os codigos e registros de seguranca gerados.
- `resolution_summary`: resumo executivo da intervencao realizada.
- `escalation_team`: equipe acionada caso aplicavel (ou null).
"""


class RemediationAgentRunner:
    """
    Executor do Agente 2 de Remediacao e Despacho N2.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def run(self, request: RemediationRequest) -> RemediationResponse:
        """
        Executa a esteira de remediacao com base nos dados do chamado triado.
        """
        remediation_id = f"REM-{uuid.uuid4().hex[:8].upper()}"
        actions_list: List[RemediationAction] = []
        audit_trail: List[str] = []
        overall_status = "SUCCESS"
        escalation_team = None
        sla_target = 120  # default Alta

        # 1. Determinacao e Execucao das Acoes via Ferramentas Python
        req_text = f"{request.category} {request.recommended_action} {request.action_type or ''}".lower()

        # Caso A: Desbloqueio de Conta
        if "unlock" in req_text or "desbloqueio" in req_text or "bloqueada" in req_text or request.category == "Acessos/Senhas":
            tool_res = json.loads(unlock_user_account(request.user_email, reason=f"Chamado {request.ticket_id}"))
            audit_trail.append(f"AD_UNLOCK: {tool_res['audit_code']} - {tool_res['email']}")
            actions_list.append(RemediationAction(
                action_name="unlock_user_account",
                target=request.user_email,
                status=tool_res["status"],
                message=tool_res["message"],
                timestamp=tool_res["timestamp"]
            ))

        # Caso B: Rota de VPN de Contingencia
        if "vpn" in req_text or "gateway" in req_text or request.category == "Redes/VPN":
            tool_vpn = json.loads(configure_vpn_failover_route(request.user_email, gateway="BR-SA-02"))
            audit_trail.append(f"VPN_ROUTE: {tool_vpn['session_token']} -> {tool_vpn['target_gateway']}")
            actions_list.append(RemediationAction(
                action_name="configure_vpn_failover_route",
                target=tool_vpn["target_gateway"],
                status=tool_vpn["status"],
                message=tool_vpn["message"],
                timestamp=tool_vpn["timestamp"]
            ))

        # Caso C: Escalonamento Humano / Despacho N2
        if request.requires_human_escalation or "hardware" in req_text:
            overall_status = "ESCALATED"
            escalation_team = "N2 Infraestrutura" if "vpn" in req_text or "rede" in req_text else (
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
            actions_list.append(RemediationAction(
                action_name="dispatch_sla_incident",
                target=escalation_team,
                status=tool_itsm["status"],
                message=f"Incidente {tool_itsm['incident_number']} criado para {escalation_team}. SLA: {sla_target} min.",
                timestamp=tool_itsm["dispatched_at"]
            ))
        else:
            # Se nao houve escalonamento e foi bem sucedido, SLA de auto-resolucao e imediato
            sla_target = 15

        # 2. Sintese via LLM ou Composicao Deterministica
        summary_prompt = f"""
        Ticket: {request.ticket_id} | Usuario: {request.user_email} | Categoria: {request.category}
        Acoes Executadas: {[a.model_dump() for a in actions_list]}
        Status Geral: {overall_status}
        """

        try:
            response = await self.client.chat.completions.create(
                model="ag/claude-sonnet-4-6",
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

            return RemediationResponse(
                remediation_id=remediation_id,
                ticket_id=request.ticket_id,
                status=parsed_data.get("status", overall_status),
                actions_executed=actions_list,
                sla_target_minutes=parsed_data.get("sla_target_minutes", sla_target),
                audit_trail=audit_trail,
                resolution_summary=parsed_data.get("resolution_summary", f"Operacoes concluidas com sucesso para {request.user_email}."),
                escalation_team=parsed_data.get("escalation_team", escalation_team)
            )
        except Exception:
            # Contingencia deterministica
            summary_msg = f"Remediacao executada com sucesso para o chamado {request.ticket_id}. "
            if overall_status == "ESCALATED":
                summary_msg += f"Conta/servico mitigado e chamado direcionado para a equipe {escalation_team} com SLA de {sla_target} minutos."
            else:
                summary_msg += f"Conta corporativa {request.user_email} desbloqueada e ativa no Active Directory."

            return RemediationResponse(
                remediation_id=remediation_id,
                ticket_id=request.ticket_id,
                status=overall_status,
                actions_executed=actions_list,
                sla_target_minutes=sla_target,
                audit_trail=audit_trail,
                resolution_summary=summary_msg,
                escalation_team=escalation_team
            )

    def _clean_json_string(self, content: str) -> str:
        content = content.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if match:
            return match.group(1).strip()
        return content
