"""
Calibração do limiar de similaridade do RAG do Agente 1 (embeddings reais via proxy).
Grava tests/results/rag_calibration.json com a similaridade top-1 de consultas relevantes
e irrelevantes. Uso: python tests/calibrate_rag.py
"""
import json, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agent1.rag import VectorEmbeddingRAG

RELEVANT = [
    ("vpn caindo home office", "KB-102"),
    ("A VPN corporativa cai a cada 5 minutos desde cedo", "KB-102"),
    ("computador nao liga tela preta LED apagado", "KB-103"),
    ("erro 403 folha conta bloqueada", "KB-101"),
    ("conta bloqueada Active Directory redefinicao senha", "KB-104"),
    ("esqueci minha senha do outlook", "KB-104"),
    ("Nao consigo acessar a folha de pagamento, erro 403", "KB-101"),
]
IRRELEVANT = [
    "impressora do terceiro andar sem toner",
    "como pedir ferias no RH",
    "quero trocar meu mouse por um sem fio",
    "o cafe da copa acabou",
    "excel travando ao abrir planilha grande",
]

def main():
    rag = VectorEmbeddingRAG(min_similarity=0.0)
    out = {"embedding_model": rag.embedding_model, "dimensions": rag.dimensions, "relevant": [], "irrelevant": []}
    for q, expected in RELEVANT:
        top = rag.retrieve(q, top_k=4)
        out["relevant"].append({"query": q, "expected": expected, "top1": top[0][0]["id"], "score": top[0][1],
                                "correct": top[0][0]["id"] == expected})
    for q in IRRELEVANT:
        top = rag.retrieve(q, top_k=4)
        out["irrelevant"].append({"query": q, "top1": top[0][0]["id"], "score": top[0][1]})
    rel_min = min(r["score"] for r in out["relevant"])
    irr_max = max(r["score"] for r in out["irrelevant"])
    out["summary"] = {"relevant_min": rel_min, "irrelevant_max": irr_max,
                      "chosen_threshold": round((rel_min + irr_max) / 2, 2),
                      "top1_accuracy": sum(r["correct"] for r in out["relevant"]) / len(RELEVANT)}
    path = os.path.join(os.path.dirname(__file__), "results", "rag_calibration.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(out["summary"], ensure_ascii=False))

if __name__ == "__main__":
    main()
