"""
Modelos Pydantic v2 do Agente 2 (Auto-Remediação e Despacho N2).

TP5: o contrato de entrada ficou estrito — o Agente 2 executa AÇÕES PRIVILEGIADAS, então
a validação acontece antes de qualquer ferramenta:
  * user_email precisa ser @empresa.com (antes aceitava 'atacante@gmail.com' e executava
    unlock_user_account nele); pontuação final é removida ('maria.souza@empresa.com.').
  * category / severity / action_type viraram Literal, com normalização de acentos
    ('Média' gerava SLA 240 min, um valor que não existe na matriz oficial).
  * Novo campo `planned_actions` na saída e status SKIPPED/BLOCKED nas ações.
"""
import re
import unicodedata
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Category = Literal["Hardware", "Software", "Redes/VPN", "Acessos/Senhas", "Outros"]
Severity = Literal["Baixa", "Media", "Alta", "Critica"]
ActionType = Literal["UNLOCK_ACCOUNT", "VPN_FAILOVER", "DISPATCH_INCIDENT", "AUTO_DETECT"]

CORPORATE_EMAIL_RE = re.compile(r"^[a-z0-9_.+-]+@empresa\.com$")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


_CATEGORY = {"hardware": "Hardware", "software": "Software", "redes/vpn": "Redes/VPN", "redes": "Redes/VPN",
             "vpn": "Redes/VPN", "acessos/senhas": "Acessos/Senhas", "acessos": "Acessos/Senhas", "outros": "Outros"}
_SEVERITY = {"baixa": "Baixa", "media": "Media", "alta": "Alta", "critica": "Critica"}


class RemediationRequest(BaseModel):
    """Payload de POST /run do Agente 2 (dados estruturados vindos do n8n)."""
    ticket_id: str = Field(..., min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$",
                           description="Identificador do ticket gerado pelo orquestrador.", examples=["TCK-40301-BR"])
    user_email: Optional[str] = Field(default=None, description="E-mail corporativo (@empresa.com) do colaborador. "
                                      "Opcional: sem e-mail, ações sobre a conta viram DISPATCH_INCIDENT.",
                                      examples=["maria.souza@empresa.com"])
    category: Category = Field(..., description="Categoria da triagem N1.", examples=["Acessos/Senhas"])
    severity: Severity = Field(..., description="Severidade da triagem N1 (sem acento).", examples=["Alta"])
    recommended_action: str = Field(..., min_length=3, max_length=4000,
                                    description="Ação recomendada pela triagem (texto informativo, NÃO é comando).")
    requires_human_escalation: bool = Field(default=False, description="Se exige despacho ITSM para N2/N3.")
    action_type: Optional[ActionType] = Field(default=None, description="Intervenção decidida pelo Supervisor do n8n.",
                                              examples=["UNLOCK_ACCOUNT"])

    @field_validator("user_email", mode="before")
    @classmethod
    def _corporate_email(cls, v):
        if v in (None, ""):
            return None
        email = str(v).strip().lower().rstrip(".,;:")
        if not CORPORATE_EMAIL_RE.match(email):
            raise ValueError("user_email deve ser um e-mail corporativo @empresa.com")
        return email

    @field_validator("category", mode="before")
    @classmethod
    def _norm_category(cls, v):
        return _CATEGORY.get(strip_accents(v).strip().lower(), v) if isinstance(v, str) else v

    @field_validator("severity", mode="before")
    @classmethod
    def _norm_severity(cls, v):
        return _SEVERITY.get(strip_accents(v).strip().lower(), v) if isinstance(v, str) else v

    @field_validator("action_type", mode="before")
    @classmethod
    def _norm_action(cls, v):
        if v in (None, "", "NONE"):
            return None
        return str(v).strip().upper()


class RemediationAction(BaseModel):
    """Registro individual de uma ação executada (ou recusada) pelo agente."""
    action_name: str = Field(description="Ferramenta ou procedimento.")
    target: str = Field(description="Alvo da ação (usuário, gateway, fila).")
    status: Literal["SUCCESS", "DISPATCHED", "SKIPPED", "BLOCKED", "FAILED"] = Field(description="Resultado da ação.")
    message: str = Field(description="Detalhe técnico do resultado.")
    timestamp: str = Field(description="Timestamp ISO da execução.")


class RemediationResponse(BaseModel):
    """Saída estruturada do Agente 2."""
    remediation_id: str = Field(description="Identificador único da operação (REM-XXXXXXXX).")
    ticket_id: str = Field(description="Ticket associado.")
    status: Literal["SUCCESS", "PARTIAL", "ESCALATED", "REJECTED"] = Field(description="Resultado geral.")
    planned_actions: List[str] = Field(default_factory=list, description="Ações decididas pela política determinística.")
    actions_executed: List[RemediationAction] = Field(default_factory=list, description="Ações executadas/recusadas.")
    sla_target_minutes: int = Field(description="Meta de atendimento em minutos (matriz oficial).")
    audit_trail: List[str] = Field(default_factory=list, description="Códigos de auditoria e hashes de compliance.")
    resolution_summary: str = Field(description="Resumo executivo da intervenção.")
    summary_source: Literal["llm", "template"] = Field(default="llm",
                                                       description="Origem do resumo (template = LLM indisponível).")
    escalation_team: Optional[str] = Field(default=None, description="Equipe acionada no ITSM, se houver.")


class TaskInitiatedResponse(BaseModel):
    task_id: str = Field(description="ID único da tarefa no Agente 2.")
    status: str = Field(default="pending", description="Status inicial (pending).")
    message: str = Field(default="Operacao de remediacao iniciada em background.", description="Mensagem informativa.")


class TaskStatusResponse(BaseModel):
    task_id: str = Field(description="Identificador único da tarefa.")
    status: Literal["pending", "done", "error"] = Field(description="Status atual.")
    created_at: str = Field(description="Timestamp ISO do início.")
    completed_at: Optional[str] = Field(default=None, description="Timestamp ISO da conclusão.")
    result: Optional[RemediationResponse] = Field(default=None, description="Resultado tipado quando concluído.")
    error: Optional[str] = Field(default=None, description="Descrição do erro, se houver.")
