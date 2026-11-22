"""
Runner do Agente 2 (Auto-Remediação e Despacho N2).

Arquitetura (TP5): DECISÃO DETERMINÍSTICA + REDAÇÃO PELO LLM
  1. `plan_actions()` decide QUAIS ferramentas rodar usando só campos estruturados
     (action_type, category, requires_human_escalation) — o texto livre `recommended_action`
     NUNCA aciona ação privilegiada.
  2. As ferramentas executam (com hook PostToolUse) e geram a trilha de auditoria.
  3. O LLM só redige `resolution_summary`. Ele não pode alterar status, SLA nem equipe:
     esses campos vêm das ferramentas. Se o LLM falhar, o resumo vem de template e
     `summary_source="template"` deixa isso explícito.

Por que mudou (comportamento observado — tests/results/baseline_pre_tp5.json e execution_log.json):
  * A detecção por substring em texto livre ("bloqueada" in recommended_action) fazia o Agente 2
    DESBLOQUEAR a conta mesmo quando a triagem dizia "desbloqueio exige confirmação de identidade
    por telefone (KB-104)" e pedia escalonamento — 7 de 7 execuções do TP4.
  * "rede" in "redefinição de senha" roteava casos de acesso para "N2 Infraestrutura" (4 de 7).
  * O LLM sobrescrevia campos de controle: SLA 15 min (inexistente na matriz) e equipes
    inventadas como "SOC-TIER2-SECURITY-FORENSICS".
  * Rodada 2 (revisão do Claude Code em agent2/): matriz action_type×category; fallback para
    incidente quando a ação automática falha; log append-only (JSONL); idempotência por
    ticket_id (app.py); redator sem o texto do Agente 1 (o resumo repetia alegações não
    verificadas como fatos, ex.: "o grupo Folha_Pagamento_Admin já está atribuído").
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agent2.models import RemediationAction, RemediationRequest, RemediationResponse
from agent2.tools import (
    SLA_MATRIX_MINUTES,
    configure_vpn_failover_route,
    dispatch_sla_incident,
    unlock_user_account,
)

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

PROMPT_VERSION = "v3-tp5"

# Ação automática permitida por categoria (o Supervisor não pode pedir unlock para Hardware etc.)
ALLOWED_ACTION_BY_CATEGORY: Dict[str, str] = {"UNLOCK_ACCOUNT": "Acessos/Senhas", "VPN_FAILOVER": "Redes/VPN"}

TEAM_BY_CATEGORY: Dict[str, str] = {
    "Acessos/Senhas": "N2 Acessos e Identidade",
    "Redes/VPN": "N2 Infraestrutura e Redes",
    "Hardware": "Suporte Presencial N2",
    "Software": "N2 Aplicacoes",
    "Outros": "N1 Suporte Geral",
}

AGENT2_SYSTEM_PROMPT = """
Você é o redator de relatórios do Agente 2 (Remediação N2).
As ações JÁ FORAM executadas por ferramentas determinísticas; você apenas as descreve.

Regras:
- Escreva `resolution_summary` em português, 2 a 4 frases, para um analista de TI.
- Use SOMENTE os campos do bloco DADOS. Não invente ações, equipes, prazos, códigos, causas ou
  recomendações. Não diga que o problema foi "resolvido": descreva o que foi executado.
- Copie nomes de equipes e códigos LITERALMENTE como aparecem nos DADOS.
- Se uma ação estiver BLOCKED, FAILED ou SKIPPED, diga claramente que ela não foi executada e o motivo
  que está em `message`.
- Responda APENAS com JSON: {"resolution_summary": "..."}
"""

_JSON_BLOCK = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")


def plan_actions(req: RemediationRequest) -> Tuple[List[str], str]:
    """
    Política determinística do Agente 2. Retorna (ações, motivo).

    Regras, em ordem:
      1. Escalonamento humano exigido → só DISPATCH_INCIDENT (nenhuma ação automática:
         a triagem pediu um humano, então o Agente 2 não age sobre a conta).
      2. action_type explícito do Supervisor (UNLOCK_ACCOUNT / VPN_FAILOVER / DISPATCH_INCIDENT).
      3. AUTO_DETECT ou ausente → pela categoria (Acessos/Senhas→unlock, Redes/VPN→failover,
         demais→dispatch).
      4. Ação sobre conta/VPN sem e-mail corporativo → DISPATCH_INCIDENT (fallback seguro).
      5. (rodada 2) action_type incompatível com a categoria (ex.: UNLOCK_ACCOUNT para Hardware)
         → DISPATCH_INCIDENT.
    Depois da execução, se a ação automática terminar em FAILED/BLOCKED, o runner abre um
    incidente de fallback para o chamado não ficar sem dono.
    """
    if req.requires_human_escalation:
        return ["DISPATCH_INCIDENT"], "Triagem exige intervenção humana: abrir incidente ITSM, sem ação automática."
    if req.action_type in ("UNLOCK_ACCOUNT", "VPN_FAILOVER", "DISPATCH_INCIDENT"):
        action, reason = req.action_type, f"Ação definida pelo Supervisor do n8n: {req.action_type}."
        allowed_cat = ALLOWED_ACTION_BY_CATEGORY.get(action)
        if allowed_cat and req.category != allowed_cat:
            return ["DISPATCH_INCIDENT"], (f"Conflito action_type×category ({action} para {req.category}): "
                                           "ação automática recusada, incidente ITSM aberto.")
    else:
        by_category = {"Acessos/Senhas": "UNLOCK_ACCOUNT", "Redes/VPN": "VPN_FAILOVER"}
        action = by_category.get(req.category, "DISPATCH_INCIDENT")
        reason = f"AUTO_DETECT pela categoria {req.category}: {action}."
    if action in ("UNLOCK_ACCOUNT", "VPN_FAILOVER") and not req.user_email:
        return ["DISPATCH_INCIDENT"], f"{action} exige e-mail corporativo, ausente no chamado: incidente ITSM aberto."
    return [action], reason


class RemediationAgentRunner:
    """Executor do Agente 2."""

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_path = os.path.join(base_dir, "execution_log.jsonl")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
        self.model_name = os.getenv("MODEL_NAME", "ag/claude-sonnet-4-6")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=45.0)

    async def run(self, request: RemediationRequest) -> RemediationResponse:
        start_time = datetime.now(timezone.utc)
        remediation_id = f"REM-{uuid.uuid4().hex[:8].upper()}"
        planned, plan_reason = plan_actions(request)
        actions: List[RemediationAction] = []
        audit_trail: List[str] = [f"POLICY: {plan_reason}"]
        escalation_team = None
        sla_target = SLA_MATRIX_MINUTES[request.severity.lower()]

        queue = list(planned)
        while queue:
            action = queue.pop(0)
            if action == "UNLOCK_ACCOUNT":
                res = json.loads(unlock_user_account(request.user_email, reason=f"Chamado {request.ticket_id}"))
                audit_trail.append(f"AD_UNLOCK[{res['status']}]: {res['audit_code']} - {res['email']}")
                actions.append(RemediationAction(action_name="unlock_user_account", target=res["email"],
                                                 status=res["status"], message=res["message"], timestamp=res["timestamp"]))
            elif action == "VPN_FAILOVER":
                res = json.loads(configure_vpn_failover_route(request.user_email, gateway="BR-SA-02", ticket_id=request.ticket_id))
                audit_trail.append(f"VPN_ROUTE[{res['status']}]: {res.get('session_token')} -> {res['target_gateway']}")
                actions.append(RemediationAction(action_name="configure_vpn_failover_route", target=res["target_gateway"],
                                                 status=res["status"], message=res["message"], timestamp=res["timestamp"]))
            elif action == "DISPATCH_INCIDENT":
                escalation_team = TEAM_BY_CATEGORY[request.category]
                res = json.loads(dispatch_sla_incident(request.ticket_id, request.severity, escalation_team,
                                                       request.recommended_action))
                if res.get("sla_target_minutes"):
                    sla_target = res["sla_target_minutes"]
                audit_trail.append(f"ITSM_DISPATCH[{res['status']}]: {res.get('incident_number')} SLA: {sla_target}min")
                msg = (f"Incidente {res['incident_number']} criado para {escalation_team}. SLA: {sla_target} min."
                       if res["status"] == "DISPATCHED" else res.get("message", "Falha no despacho."))
                actions.append(RemediationAction(action_name="dispatch_sla_incident", target=escalation_team,
                                                 status=res["status"], message=msg, timestamp=res["dispatched_at"]))
            if "compliance_hash" in res:
                audit_trail.append(f"HOOK_POST_TOOL: {res['compliance_hash']}")
            # fallback: ação automática recusada/falhou → incidente para um humano assumir
            if action != "DISPATCH_INCIDENT" and res.get("status") in ("FAILED", "BLOCKED") and "DISPATCH_INCIDENT" not in planned:
                planned.append("DISPATCH_INCIDENT")
                queue.append("DISPATCH_INCIDENT")
                audit_trail.append(f"POLICY: {action} terminou em {res['status']}; incidente de fallback aberto.")

        overall = self._overall_status(actions)
        summary, source = await self._summarize(request, actions, overall, sla_target, escalation_team)

        response = RemediationResponse(
            remediation_id=remediation_id, ticket_id=request.ticket_id, status=overall,
            planned_actions=planned, actions_executed=actions, sla_target_minutes=sla_target,
            audit_trail=audit_trail, resolution_summary=summary, summary_source=source,
            escalation_team=escalation_team,
        )
        self._record_execution_log(request, response, start_time)
        return response

    @staticmethod
    def _overall_status(actions: List[RemediationAction]) -> str:
        statuses = {a.status for a in actions}
        if "DISPATCHED" in statuses:
            return "ESCALATED"
        if statuses and statuses <= {"BLOCKED", "FAILED"}:
            return "REJECTED"
        if statuses & {"BLOCKED", "FAILED"}:
            return "PARTIAL"
        return "SUCCESS"

    async def _summarize(self, req, actions, overall, sla, team) -> Tuple[str, str]:
        data = {
            "ticket_id": req.ticket_id, "user_email": req.user_email, "category": req.category,
            "severity": req.severity, "status_geral": overall, "sla_target_minutes": sla, "escalation_team": team,
            "acoes": [a.model_dump() for a in actions],
        }
        try:
            resp = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": AGENT2_SYSTEM_PROMPT},
                          {"role": "user", "content": "DADOS:\n" + json.dumps(data, ensure_ascii=False)}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = (resp.choices[0].message.content or "").strip()
            m = _JSON_BLOCK.search(content)
            parsed = json.loads(m.group(1) if m else content)
            summary = str(parsed["resolution_summary"]).strip()
            if summary:
                return summary, "llm"
        except Exception:  # noqa: BLE001 - o resumo é cosmético; as ações já estão registradas
            pass
        parts = [f"{a.action_name}: {a.status} — {a.message}" for a in actions]
        return f"Chamado {req.ticket_id} ({overall}). " + " | ".join(parts), "template"

    def _record_execution_log(self, request: RemediationRequest, response: RemediationResponse, start_time: datetime):
        """Append-only (JSON Lines): uma linha por execução; nunca reescreve o histórico."""
        completed = datetime.now(timezone.utc)
        entry = {
            "timestamp": completed.isoformat(),
            "duration_seconds": round((completed - start_time).total_seconds(), 3),
            "request": request.model_dump(),
            "response": response.model_dump(),
            "agent_model": self.model_name,
            "prompt_version": PROMPT_VERSION,
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as ex:  # noqa: BLE001
            print(f"Aviso: falha ao gravar log do Agente 2: {ex}")
