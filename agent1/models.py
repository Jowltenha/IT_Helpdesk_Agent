"""
Modelos Pydantic v2 para o Agente 1 (Triagem de TI Nivel 1).
Define contratos de entrada, saida e schemas de tarefas assincronas.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Payload de requisicao para o endpoint POST /run."""
    user_prompt: str = Field(
        ...,
        description="Texto do chamado relatado pelo colaborador.",
        example="Nao consigo acessar a folha de pagamento. Erro 403. Urgente ate 17h."
    )
    session_id: Optional[str] = Field(
        default="default_session",
        description="Identificador da sessao para manutencao da memoria persistente.",
        example="user_maria_session_01"
    )


class SystemStatus(BaseModel):
    """Modelo representando o status de um servico corporativo."""
    service_name: str = Field(description="Nome do servico (ex: VPN, Folha, ERP).")
    status: str = Field(description="Status operacional: Operational, Degradado, Indisponivel ou Manutencao.")
    message: str = Field(description="Detalhes ou mensagem oficial do estado do servico.")
    last_updated: str = Field(description="Timestamp da ultima verificacao.")


class UserPermission(BaseModel):
    """Modelo representando perfil e permissoes de um colaborador."""
    email: str = Field(description="E-mail corporativo do usuario.")
    name: str = Field(description="Nome completo do colaborador.")
    role: str = Field(description="Cargo ou funcao.")
    groups: List[str] = Field(description="Grupos de acesso aos quais o usuario pertence.")
    account_locked: bool = Field(description="Indica se a conta esta bloqueada no Active Directory.")


class KnowledgeArticle(BaseModel):
    """Modelo de artigo de suporte recuperado via RAG."""
    article_id: str = Field(description="Identificador unico do artigo.")
    title: str = Field(description="Titulo do artigo da Base de Conhecimento.")
    category: str = Field(description="Categoria associada.")
    solution: str = Field(description="Procedimento passo a passo para resolucao.")
    relevance_score: float = Field(description="Pontuacao de relevancia semantica (0.0 a 1.0).")


class HelpdeskResponse(BaseModel):
    """
    Modelo de saida estruturada e validada do Agente de Triagem de TI N1.
    Combina classificacao, recomendacao, rastreamento de raciocinio CoT e ferramentas.
    """
    ticket_summary: str = Field(
        description="Resumo claro e conciso do problema relatado em ate 10 palavras."
    )
    category: str = Field(
        description="Categoria do chamado: Hardware, Software, Redes/VPN, Acessos/Senhas ou Outros."
    )
    severity: str = Field(
        description="Nivel de severidade: Baixa, Media, Alta ou Critica."
    )
    recommended_action: str = Field(
        description="Passos ou recomendacoes imediatas para a resolucao do problema."
    )
    requires_human_escalation: bool = Field(
        description="True se o problema exigir intervencao presencial ou nivel N2/N3 de TI."
    )
    reasoning_steps: List[str] = Field(
        default_factory=list,
        description="Etapas de raciocinio (Chain-of-Thought) utilizadas para chegar a conclusao."
    )
    tools_invoked: List[str] = Field(
        default_factory=list,
        description="Lista de ferramentas Python consultadas durante o processamento."
    )
    confidence_score: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Pontuacao de confianca da analise entre 0.0 e 1.0."
    )


class TaskInitiatedResponse(BaseModel):
    """Resposta imediata (HTTP 202 Accepted) ao registrar uma tarefa assincrona."""
    task_id: str = Field(description="ID unico da tarefa gerada.")
    status: str = Field(default="pending", description="Status inicial da tarefa (pending).")
    message: str = Field(default="Tarefa de triagem iniciada em background.", description="Mensagem informativa.")


class TaskStatusResponse(BaseModel):
    """Modelo de consulta de status da tarefa (GET /status/{task_id})."""
    task_id: str = Field(description="Identificador unico da tarefa.")
    status: str = Field(description="Status atual: pending, done ou error.")
    created_at: str = Field(description="Timestamp ISO do inicio do processamento.")
    completed_at: Optional[str] = Field(default=None, description="Timestamp ISO da conclusao da tarefa.")
    result: Optional[HelpdeskResponse] = Field(default=None, description="Resultado tipado quando concluido.")
    error: Optional[str] = Field(default=None, description="Descricao do erro caso status seja error.")
