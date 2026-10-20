"""
Modelos Pydantic v2 para o Agente 2 (Resolucao Automatizada N2 e Remediacao de TI).
Define contratos de entrada, saida e schemas de tarefas assincronas.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RemediationRequest(BaseModel):
    """Payload de requisicao para o endpoint POST /run do Agente 2."""
    ticket_id: str = Field(
        ...,
        description="Identificador unico do ticket triado pelo Agente 1 ou orquestrador.",
        example="TCK-40301-BR"
    )
    user_email: str = Field(
        ...,
        description="E-mail corporativo do usuario que necessita de atendimento.",
        example="maria.souza@empresa.com"
    )
    category: str = Field(
        ...,
        description="Categoria definida na triagem: Hardware, Software, Redes/VPN, Acessos/Senhas.",
        example="Acessos/Senhas"
    )
    severity: str = Field(
        ...,
        description="Nivel de severidade: Baixa, Media, Alta ou Critica.",
        example="Alta"
    )
    recommended_action: str = Field(
        ...,
        description="Acao recomendada na triagem para execucao automatica ou escalonamento.",
        example="Solicitar desbloqueio da conta maria.souza@empresa.com no Active Directory."
    )
    requires_human_escalation: bool = Field(
        default=False,
        description="Indica se a acao exige despacho prioritario para suporte presencial/N3."
    )
    action_type: Optional[str] = Field(
        default=None,
        description="Tipo especifico de intervencao: UNLOCK_ACCOUNT, VPN_FAILOVER, DISPATCH_INCIDENT ou AUTO_DETECT.",
        example="UNLOCK_ACCOUNT"
    )


class RemediationAction(BaseModel):
    """Registro individual de uma acao executada pelo agente."""
    action_name: str = Field(description="Nome da ferramenta ou procedimento executado.")
    target: str = Field(description="Alvo da acao (ex: usuario, gateway, fila de atendimento).")
    status: str = Field(description="Status da acao: SUCCESS, FAILED ou SKIPPED.")
    message: str = Field(description="Detalhes tecnicos do resultado da acao.")
    timestamp: str = Field(description="Timestamp ISO da execucao.")


class RemediationResponse(BaseModel):
    """
    Modelo de saida estruturada e validada do Agente 2 de Remediacao.
    """
    remediation_id: str = Field(
        description="Identificador unico da operacao de remediacao."
    )
    ticket_id: str = Field(
        description="Ticket associado a esta execucao."
    )
    status: str = Field(
        description="Resultado geral da operacao: SUCCESS, PARTIAL ou ESCALATED."
    )
    actions_executed: List[RemediationAction] = Field(
        default_factory=list,
        description="Lista detalhada das acoes tecnicas executadas pelas ferramentas Python."
    )
    sla_target_minutes: int = Field(
        description="Tempo maximo estipulado para resolucao/atendimento em minutos."
    )
    audit_trail: List[str] = Field(
        default_factory=list,
        description="Trilha de auditoria para compliance e seguranca de informacao."
    )
    resolution_summary: str = Field(
        description="Resumo claro e conclusivo da intervencao realizada."
    )
    escalation_team: Optional[str] = Field(
        default=None,
        description="Equipe acionada caso necessite de continuidade (ex: N2 Infra, Suporte Presencial)."
    )


class TaskInitiatedResponse(BaseModel):
    """Resposta imediata (HTTP 202 Accepted) ao registrar a tarefa no Agente 2."""
    task_id: str = Field(description="ID unico da tarefa gerada no Agente 2.")
    status: str = Field(default="pending", description="Status inicial (pending).")
    message: str = Field(default="Operacao de remediacao iniciada em background.", description="Mensagem informativa.")


class TaskStatusResponse(BaseModel):
    """Modelo de consulta de status da tarefa (GET /status/{task_id}) no Agente 2."""
    task_id: str = Field(description="Identificador unico da tarefa.")
    status: str = Field(description="Status atual: pending, done ou error.")
    created_at: str = Field(description="Timestamp ISO do inicio.")
    completed_at: Optional[str] = Field(default=None, description="Timestamp ISO da conclusao.")
    result: Optional[RemediationResponse] = Field(default=None, description="Resultado tipado quando concluido.")
    error: Optional[str] = Field(default=None, description="Descricao do erro caso ocorra falha.")
