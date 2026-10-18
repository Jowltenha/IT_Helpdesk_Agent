"""
Definição dos modelos Pydantic para validação de entrada, saída e contexto do Agente de Helpdesk.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class SystemStatus(BaseModel):
    """Modelo representando o status de um sistema/serviço corporativo."""
    service_name: str = Field(description="Nome do serviço (ex: VPN, ERP, Email, Folha de Pagamento).")
    status: str = Field(description="Status operacional: Operational, Degradado, Indisponível ou Manutenção.")
    message: str = Field(description="Detalhes ou mensagem oficial do estado do serviço.")
    last_updated: str = Field(description="Timestamp da última verificação.")


class UserPermission(BaseModel):
    """Modelo representando perfil e permissões de um colaborador."""
    email: str = Field(description="E-mail corporativo do usuário.")
    name: str = Field(description="Nome completo do colaborador.")
    role: str = Field(description="Cargo ou função.")
    groups: List[str] = Field(description="Grupos de acesso aos quais o usuário pertence.")
    account_locked: bool = Field(description="Indica se a conta está bloqueada por tentativas incorretas.")


class KnowledgeArticle(BaseModel):
    """Modelo de artigo de suporte recuperado via RAG."""
    article_id: str = Field(description="Identificador único do artigo.")
    title: str = Field(description="Título do artigo da Base de Conhecimento.")
    category: str = Field(description="Categoria associada.")
    solution: str = Field(description="Procedimento passo a passo para resolução.")
    relevance_score: float = Field(description="Pontuação de relevância semântica (0.0 a 1.0).")


class HelpdeskResponse(BaseModel):
    """
    Modelo de saída estruturada e validada do Agente de Triagem de TI.
    Combina classificação, recomendação, rastreamento de raciocínio e ferramentas.
    """
    ticket_summary: str = Field(
        description="Resumo claro e conciso do problema relatado em até 10 palavras."
    )
    category: str = Field(
        description="Categoria do chamado: Hardware, Software, Redes/VPN, Acessos/Senhas ou Outros."
    )
    severity: str = Field(
        description="Nível de severidade: Baixa, Média, Alta ou Crítica."
    )
    recommended_action: str = Field(
        description="Passos ou recomendações imediatas para a resolução do problema."
    )
    requires_human_escalation: bool = Field(
        description="True se o problema exigir intervenção presencial ou nível N2/N3 de TI."
    )
    reasoning_steps: List[str] = Field(
        default_factory=list,
        description="Etapas de raciocínio (Chain-of-Thought) utilizadas para chegar à conclusão."
    )
    tools_invoked: List[str] = Field(
        default_factory=list,
        description="Lista de ferramentas Python consultadas durante o processamento."
    )
    confidence_score: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Pontuação de confiança da classificação entre 0.0 e 1.0."
    )
