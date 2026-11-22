"""
Engine RAG do Agente 1: embeddings vetoriais densos (1536 dimensões) + similaridade de cosseno.

TP5 — o que mudou e por quê:
  * O modelo `text-embedding-3-small` não existe no proxy 9Router ("No credentials for provider:
    openai"). No TP4, toda chamada caía num `except` que gerava um vetor por hash SHA-256 dos
    tokens: na prática um RAG de palavras-chave disfarçado (o mesmo tipo de fallback penalizado
    no TP2). Agora usamos `gemini-embedding-001`, servido de verdade pelo proxy, reduzido a
    1536 dimensões (Matryoshka) — configurável por EMBEDDING_MODEL / EMBEDDING_DIMENSIONS.
  * Foi removido o fallback por hash. Se o endpoint de embeddings falhar, a busca devolve
    status KB_INDISPONIVEL e o agente é instruído a dizer isso (falha explícita, nunca simulada).
  * Foi removido o "bônus" de +0.08 por palavra-chave, que inflava scores artificialmente.
  * Limiar mínimo de similaridade (RAG_MIN_SIMILARITY, padrão 0.62), calibrado em
    tests/results/rag_calibration.json: 7 consultas relevantes ficaram entre 0.643 e 0.778
    (todas com o artigo certo em 1º lugar) e 5 irrelevantes ("impressora sem toner",
    "pedir férias"...) ficaram ≤ 0.593. Abaixo do limiar nenhum artigo é devolvido, evitando
    que o modelo cite um SOP sem relação com o chamado.
  * Cada artigo ganhou "keywords" (termos que os usuários realmente escrevem, ex.: "home
    office", "esqueci a senha"), que entram no texto indexado — a busca segue 100% vetorial.
  * A base de conhecimento passou a ser fonte única: a tool `query_troubleshooting_kb`
    consulta este mesmo índice (antes ela tinha artigos fictícios próprios, KB-40301/KB-80802).
"""
import math
import os
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

KB_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "id": "KB-101",
        "title": "Resolução de Erros de Permissão 403 e Acesso Negado em Sistemas Web",
        "category": "Acessos/Senhas",
        "content": "Para erros 403 no sistema de Folha de Pagamento ou ERP: 1. Confirmar se o usuário possui perfil ativo no AD corporativo. 2. Verificar se o grupo Folha_Pagamento_Admin ou Leitura foi atribuído. 3. Caso a conta esteja bloqueada por tentativas inválidas, acionar N2 para redefinição. 4. Limpeza de cache e cookies no navegador resolve casos de sessão corrompida.",
        "keywords": "403, acesso negado, permissão, folha de pagamento, ERP, conta bloqueada, Active Directory",
    },
    {
        "id": "KB-102",
        "title": "Procedimento de Diagnóstico e Correção de VPN Corporativa",
        "category": "Redes/VPN",
        "content": "Em caso de falha de conexão ou lentidão na VPN OpenVPN: 1. Verificar o status dos gateways regionais. 2. Se o gateway principal estiver degradado, alternar a rota para o servidor secundário BR-SA-02. 3. Redefinir a pilha de rede TCP/IP com o comando netsh int ip reset. 4. Chamados urgentes devem ser escalados para N2 Infraestrutura.",
        "keywords": "VPN, conexão caindo, OpenVPN, gateway, home office, acesso remoto, lentidão, failover",
    },
    {
        "id": "KB-103",
        "title": "Falha de Hardware - Computador Não Liga ou Tela Preta",
        "category": "Hardware",
        "content": "Para incidentes de computador sem vídeo ou sem energia: 1. Testar cabo de força e fonte de alimentação. 2. Verificar se há leds acesos no gabinete ou teclado. 3. Este tipo de falha exige intervenção presencial obrigatória por analista de suporte N1/N2 físico.",
        "keywords": "hardware, tela preta, não liga, fonte, energia, computador, notebook, atendimento presencial",
    },
    {
        "id": "KB-104",
        "title": "Política de Redefinição de Senha e Desbloqueio de E-mail Corporativo",
        "category": "Acessos/Senhas",
        "content": "Para redefinição de senha do Outlook/Office 365: 1. Acessar o portal de autoatendimento pass.empresa.com. 2. Caso o usuário esteja fora da rede interna, a autenticação via MFA é obrigatória. 3. Desbloqueios manuais de conta exigem confirmação de identidade por telefone.",
        "keywords": "senha, esqueci a senha, e-mail, Outlook, Office 365, desbloqueio, MFA",
    },
]


class RAGUnavailableError(RuntimeError):
    """O endpoint de embeddings não respondeu; a busca não pode ser feita."""


class VectorEmbeddingRAG:
    """Busca semântica nos artigos da KB por embeddings densos e similaridade de cosseno."""

    def __init__(
        self,
        embedding_model: Optional[str] = None,
        dimensions: Optional[int] = None,
        min_similarity: Optional[float] = None,
    ):
        self.embedding_model = embedding_model or os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
        self.dimensions = int(dimensions or os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        self.min_similarity = float(min_similarity if min_similarity is not None else os.getenv("RAG_MIN_SIMILARITY", "0.62"))
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
        self.documents = KB_DOCUMENTS
        self.doc_embeddings: List[List[float]] = []
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=20.0)
        return self._client

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Gera embeddings reais em lote. Sem fallback simulado: falha vira RAGUnavailableError."""
        try:
            response = self.client.embeddings.create(
                input=texts, model=self.embedding_model, dimensions=self.dimensions
            )
        except Exception as exc:  # noqa: BLE001 - qualquer falha de rede/provedor
            raise RAGUnavailableError(f"Endpoint de embeddings indisponível ({self.embedding_model}): {exc}") from exc
        return [item.embedding for item in response.data]

    def _ensure_index(self) -> None:
        """Indexa a KB na primeira busca (lazy), para o serviço subir mesmo com o proxy fora do ar."""
        if self.doc_embeddings:
            return
        texts = [f"{d['title']}. {d['content']} Termos relacionados: {d['keywords']}" for d in self.documents]
        self.doc_embeddings = self._embed(texts)

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def retrieve(self, query: str, top_k: int = 2) -> List[Tuple[Dict[str, Any], float]]:
        """Top-k artigos com similaridade >= min_similarity. Lança RAGUnavailableError se não houver embeddings."""
        self._ensure_index()
        query_embedding = self._embed([query])[0]
        scored = [
            (doc, round(self._cosine_similarity(query_embedding, vec), 3))
            for doc, vec in zip(self.documents, self.doc_embeddings)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(doc, score) for doc, score in scored[:top_k] if score >= self.min_similarity]

    def format_rag_context(self, query: str, top_k: int = 2) -> str:
        """Formata os artigos recuperados como bloco de contexto para as instruções do agente."""
        header = "--- CONTEXTO PROCEDURAL (RAG KB RETRIEVAL VIA EMBEDDINGS) ---"
        try:
            results = self.retrieve(query, top_k=top_k)
        except RAGUnavailableError as exc:
            return f"{header}\nKB_INDISPONIVEL: {exc}. Informe no laudo que a Base de Conhecimento não pôde ser consultada."
        if not results:
            return (
                f"{header}\nSEM_ARTIGO_RELEVANTE: nenhum artigo atingiu similaridade >= {self.min_similarity}. "
                "Não cite IDs de artigo; recomende coleta de evidências e encaminhamento ao suporte do módulo."
            )
        lines = [header]
        for doc, score in results:
            lines.append(f"• Artigo ID: {doc['id']} | Título: {doc['title']} (Similaridade Cosseno: {score})")
            lines.append(f"  Categoria: {doc['category']}")
            lines.append(f"  Procedimento: {doc['content']}\n")
        return "\n".join(lines)


_SHARED_RAG: Optional[VectorEmbeddingRAG] = None


def get_shared_rag() -> VectorEmbeddingRAG:
    """Instância única (o índice da KB é calculado uma vez por processo)."""
    global _SHARED_RAG
    if _SHARED_RAG is None:
        _SHARED_RAG = VectorEmbeddingRAG()
    return _SHARED_RAG
