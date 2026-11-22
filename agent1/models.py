"""
Modelos Pydantic v2 do Agente 1 (Triagem de TI Nível 1).

Contém três grupos de contratos:
  1. Contrato HTTP (RunRequest, TaskInitiatedResponse, TaskStatusResponse).
  2. Contrato de saída do LLM (HelpdeskResponse) — validado pelo output_type do Agents SDK.
  3. Contratos de saída das ferramentas (SystemStatus, UserAccountResult, KBSearchResult),
     reutilizados pelas @function_tool e pelo servidor MCP (agent1/mcp/server.py).

TP5: os campos categóricos passaram de `str` livre para `Literal` com normalização
(acentos/caixa), e o laudo ganhou `user_email` e `security_flags`.
"""
import re
import unicodedata
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

CORPORATE_DOMAIN = "empresa.com"
CORPORATE_EMAIL_RE = re.compile(r"^[a-z0-9_.+-]+@empresa\.com$")

Category = Literal["Hardware", "Software", "Redes/VPN", "Acessos/Senhas", "Outros"]
Severity = Literal["Baixa", "Media", "Alta", "Critica"]

_CATEGORY_ALIASES = {
    "hardware": "Hardware",
    "software": "Software",
    "redes/vpn": "Redes/VPN",
    "redes": "Redes/VPN",
    "vpn": "Redes/VPN",
    "acessos/senhas": "Acessos/Senhas",
    "acessos": "Acessos/Senhas",
    "senhas": "Acessos/Senhas",
    "outros": "Outros",
}
_SEVERITY_ALIASES = {"baixa": "Baixa", "media": "Media", "alta": "Alta", "critica": "Critica"}


def strip_accents(text: str) -> str:
    """Remove acentos ('Média' -> 'Media', 'Crítica' -> 'Critica')."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_corporate_email(value: Optional[str]) -> Optional[str]:
    """Normaliza e-mail (minúsculas, sem espaços e sem pontuação final). Retorna None se não for corporativo."""
    if not value or not isinstance(value, str):
        return None
    email = value.strip().lower().rstrip(".,;:")
    return email if CORPORATE_EMAIL_RE.match(email) else None


# ---------------------------------------------------------------------------
# 1. Contrato HTTP
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    """Payload de requisição para o endpoint POST /run."""
    user_prompt: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="Texto do chamado relatado pelo colaborador.",
        examples=["Nao consigo acessar a folha de pagamento. Erro 403. Urgente ate 17h."],
    )
    session_id: Optional[str] = Field(
        default="default_session",
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
        description="Identificador da sessão para manutenção da memória persistente (SQLiteSession).",
        examples=["user_maria_session_01"],
    )


class TaskInitiatedResponse(BaseModel):
    """Resposta imediata (HTTP 202 Accepted) ao registrar uma tarefa assíncrona."""
    task_id: str = Field(description="ID único da tarefa gerada.")
    status: str = Field(default="pending", description="Status inicial da tarefa (pending).")
    message: str = Field(default="Tarefa de triagem iniciada em background.", description="Mensagem informativa.")


# ---------------------------------------------------------------------------
# 2. Contrato de saída do LLM
# ---------------------------------------------------------------------------
class HelpdeskResponse(BaseModel):
    """
    Laudo estruturado e validado do Agente de Triagem N1.
    Combina classificação, recomendação, rastreamento de raciocínio CoT e ferramentas.
    """
    ticket_summary: str = Field(description="Resumo claro e conciso do problema relatado em até 10 palavras.")
    category: Category = Field(description="Categoria: Hardware, Software, Redes/VPN, Acessos/Senhas ou Outros.")
    severity: Severity = Field(description="Severidade: Baixa, Media, Alta ou Critica (sem acento).")
    recommended_action: str = Field(description="Até 5 passos numerados e acionáveis para a resolução.")
    requires_human_escalation: bool = Field(
        description="True se exigir intervenção presencial, confirmação de identidade, mudança de permissão ou N2/N3."
    )
    user_email: Optional[str] = Field(
        default=None,
        description="E-mail corporativo (@empresa.com) do colaborador, se informado no chamado. Nunca invente.",
    )
    reasoning_steps: List[str] = Field(
        default_factory=list,
        description="As 4 etapas do raciocínio (Chain-of-Thought), uma frase curta por etapa.",
    )
    tools_invoked: List[str] = Field(
        default_factory=list, description="Ferramentas Python consultadas durante o processamento."
    )
    security_flags: List[str] = Field(
        default_factory=list,
        description="Preenchido pelo sistema (guardrail de entrada). O modelo deve deixar vazio.",
    )
    confidence_score: float = Field(default=0.9, ge=0.0, le=1.0, description="Confiança da análise (0.0 a 1.0).")

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, v):
        if isinstance(v, str):
            return _CATEGORY_ALIASES.get(strip_accents(v).strip().lower(), v)
        return v

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, v):
        if isinstance(v, str):
            return _SEVERITY_ALIASES.get(strip_accents(v).strip().lower(), v)
        return v

    @field_validator("user_email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        return normalize_corporate_email(v)


class TaskStatusResponse(BaseModel):
    """Modelo de consulta de status da tarefa (GET /status/{task_id})."""
    task_id: str = Field(description="Identificador único da tarefa.")
    status: Literal["pending", "done", "error"] = Field(description="Status atual: pending, done ou error.")
    created_at: str = Field(description="Timestamp ISO do início do processamento.")
    completed_at: Optional[str] = Field(default=None, description="Timestamp ISO da conclusão da tarefa.")
    result: Optional[HelpdeskResponse] = Field(default=None, description="Resultado tipado quando concluído.")
    error: Optional[str] = Field(default=None, description="Descrição do erro caso status seja error.")


# ---------------------------------------------------------------------------
# 3. Contratos de saída das ferramentas (compartilhados com o servidor MCP)
# ---------------------------------------------------------------------------
class SystemStatus(BaseModel):
    """Saída de check_system_status."""
    service_key: Optional[str] = Field(default=None, description="Chave canônica do serviço (vpn, folha, email, erp).")
    service_name: str = Field(description="Nome do serviço consultado.")
    status: Literal["Operational", "Degradado", "Indisponivel", "Manutencao", "Desconhecido", "NEGADO_PELO_HOOK"] = Field(
        description="Status operacional do serviço."
    )
    message: str = Field(description="Detalhes ou mensagem oficial do estado do serviço.")
    last_updated: str = Field(description="Timestamp da última verificação (ou N/A).")
    monitored_services: List[str] = Field(
        default_factory=list, description="Serviços válidos, devolvidos quando o nome pedido não é reconhecido."
    )


class UserAccountResult(BaseModel):
    """Saída de lookup_user_account."""
    email: str = Field(description="E-mail consultado (normalizado).")
    found: bool = Field(description="True se a conta existe no Active Directory.")
    status: Literal["ENCONTRADO", "NAO_ENCONTRADO", "NEGADO_PELO_HOOK"] = Field(description="Resultado da consulta.")
    name: Optional[str] = Field(default=None, description="Nome completo do colaborador.")
    role: Optional[str] = Field(default=None, description="Cargo ou função.")
    groups: List[str] = Field(default_factory=list, description="Grupos de acesso do usuário no AD.")
    account_locked: Optional[bool] = Field(
        default=None, description="True/False se a conta existe; None quando a consulta não pôde ser feita."
    )
    message: str = Field(default="", description="Mensagem explicativa.")


class KnowledgeArticle(BaseModel):
    """Artigo da Base de Conhecimento recuperado via RAG."""
    article_id: str = Field(description="Identificador único do artigo (KB-101 a KB-104).")
    title: str = Field(description="Título do artigo.")
    category: str = Field(description="Categoria associada.")
    solution: str = Field(description="Procedimento passo a passo para resolução.")
    relevance_score: float = Field(ge=0.0, le=1.0, description="Similaridade de cosseno com a consulta.")


class KBSearchResult(BaseModel):
    """Saída de query_troubleshooting_kb."""
    query: str = Field(description="Consulta efetivamente executada (após sanitização do hook).")
    status: Literal["ENCONTRADO", "SEM_ARTIGO_RELEVANTE", "KB_INDISPONIVEL", "NEGADO_PELO_HOOK"] = Field(
        description="Resultado da busca."
    )
    articles: List[KnowledgeArticle] = Field(default_factory=list, description="Artigos acima do limiar de similaridade.")
    min_similarity: float = Field(description="Limiar mínimo de similaridade aplicado.")
    message: str = Field(default="", description="Mensagem explicativa.")
