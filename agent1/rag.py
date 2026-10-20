"""
Engine RAG (Retrieval-Augmented Generation) com busca vetorial TF-IDF + Cosseno para o Agente 1.
"""
import math
import re
from typing import List, Dict, Any, Tuple


class VectorEmbeddingRAG:
    """
    Pipeline RAG autocontido para busca semantica de artigos e procedimentos da Base de Conhecimento.
    """

    def __init__(self):
        self.documents: List[Dict[str, Any]] = [
            {
                "id": "KB-101",
                "title": "Resolucao de Erros de Permissao 403 e Acesso Negado em Sistemas Web",
                "category": "Acessos/Senhas",
                "content": "Para erros 403 no sistema de Folha de Pagamento ou ERP: 1. Confirmar se o usuario possui perfil ativo no AD corporativo. 2. Verificar se o grupo Folha_Pagamento_Admin ou Leitura foi atribuido. 3. Caso a conta esteja bloqueada por tentativas invalidas, acionar N2 para redefinicao. 4. Limpeza de cache e cookies no navegador resolve casos de sessao corrompida.",
                "keywords": ["403", "acesso negado", "permissao", "folha", "pagamento", "bloqueada"]
            },
            {
                "id": "KB-102",
                "title": "Procedimento de Diagnostico e Correcao de VPN Corporativa",
                "category": "Redes/VPN",
                "content": "Em caso de falha de conexao ou lentidao na VPN OpenVPN: 1. Verificar o status dos gateways regionais. 2. Se o gateway principal estiver degradado, alternar a rota para o servidor secundario BR-SA-02. 3. Redefinir a pilha de rede TCP/IP com o comando netsh int ip reset. 4. Chamados urgentes devem ser escalados para N2 Infraestrutura.",
                "keywords": ["vpn", "conexao", "openvpn", "gateway", "degradado", "rede", "lentidao"]
            },
            {
                "id": "KB-103",
                "title": "Falha de Hardware - Computador Nao Liga ou Tela Preta",
                "category": "Hardware",
                "content": "Para incidentes de computador sem video ou sem energia: 1. Testar cabo de forca e fonte de alimentacao. 2. Verificar se ha leds acesos no gabinete ou teclado. 3. Este tipo de falha exige intervencao presencial obrigatoria por analista de suporte N1/N2 fisico.",
                "keywords": ["hardware", "tela preta", "nao liga", "fonte", "energia", "computador"]
            },
            {
                "id": "KB-104",
                "title": "Politica de Redefinicao de Senha e Desbloqueio de E-mail Corporativo",
                "category": "Acessos/Senhas",
                "content": "Para redefinicao de senha do Outlook/Office 365: 1. Acessar o portal de autoatendimento pass.empresa.com. 2. Caso o usuario esteja fora da rede interna, a autenticacao via MFA e obrigatoria. 3. Desbloqueios manuais de conta exigem confirmacao de identidade por telefone.",
                "keywords": ["senha", "email", "outlook", "desbloqueio", "mfa", "office365", "esqueci"]
            }
        ]
        self.vocabulary: List[str] = []
        self.doc_vectors: List[List[float]] = []
        self._build_index()

    def _tokenize(self, text: str) -> List[str]:
        text_clean = re.sub(r"[^\w\s]", "", text.lower())
        return [w for w in text_clean.split() if len(w) > 2]

    def _build_index(self):
        vocab_set = set()
        tokenized_docs = []

        for doc in self.documents:
            full_text = f"{doc['title']} {doc['content']} {' '.join(doc['keywords'])}"
            tokens = self._tokenize(full_text)
            tokenized_docs.append(tokens)
            vocab_set.update(tokens)

        self.vocabulary = sorted(list(vocab_set))
        num_docs = len(self.documents)

        for tokens in tokenized_docs:
            vector = []
            for term in self.vocabulary:
                tf = tokens.count(term) / max(1, len(tokens))
                docs_with_term = sum(1 for d_tokens in tokenized_docs if term in d_tokens)
                idf = math.log((1 + num_docs) / (1 + docs_with_term)) + 1
                vector.append(tf * idf)
            self.doc_vectors.append(vector)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = math.sqrt(sum(a * a for a in vec1))
        norm_b = math.sqrt(sum(b * b for b in vec2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def retrieve(self, query: str, top_k: int = 2) -> List[Tuple[Dict[str, Any], float]]:
        query_tokens = self._tokenize(query)
        num_docs = len(self.documents)
        query_vector = []

        for term in self.vocabulary:
            tf = query_tokens.count(term) / max(1, len(query_tokens))
            docs_with_term = sum(1 for doc in self.documents if term in (doc['keywords'] + self._tokenize(doc['content'])))
            idf = math.log((1 + num_docs) / (1 + docs_with_term)) + 1
            query_vector.append(tf * idf)

        scores = []
        for idx, doc_vec in enumerate(self.doc_vectors):
            similarity = self._cosine_similarity(query_vector, doc_vec)
            doc = self.documents[idx]
            for kw in doc["keywords"]:
                if kw in query.lower():
                    similarity += 0.15
            scores.append((doc, round(min(1.0, similarity), 3)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def format_rag_context(self, query: str, top_k: int = 2) -> str:
        results = self.retrieve(query, top_k=top_k)
        if not results:
            return "Nenhum artigo relevante encontrado na Base de Conhecimento."

        context_lines = ["--- CONTEXTO PROCEDURAL (RAG KB RETRIEVAL) ---"]
        for doc, score in results:
            context_lines.append(f" Artigo ID: {doc['id']} | Titulo: {doc['title']} (Relevancia: {score})")
            context_lines.append(f" Categoria: {doc['category']}")
            context_lines.append(f" Procedimento: {doc['content']}\n")

        return "\n".join(context_lines)
