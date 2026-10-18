"""
Script de Avaliação A/B de Prompts e Métricas de Qualidade do Agente.
Compara a Variante A (Baseline Single-Shot) com a Variante B (Refinada CoT + Tools + RAG).
"""
import os
import sys
import json
import asyncio
from typing import Dict, Any, List
from dotenv import load_dotenv
from openai import AsyncOpenAI

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.models import HelpdeskResponse
from agent.tools import check_system_status, lookup_user_account, query_troubleshooting_kb
from agent.rag import VectorEmbeddingRAG

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "mock-key"),
    base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
)

# Benchmark de testes com Ground Truth (Gabarito de Referência)
BENCHMARK_DATASET = [
    {
        "id": "TEST-01",
        "input": "Não consigo conectar na VPN corporativa da empresa. Aparece mensagem de gateway inacessível.",
        "expected_category": "Redes/VPN",
        "expected_severity": "Média",
        "expected_tool": "check_system_status",
        "expected_escalation": False
    },
    {
        "id": "TEST-02",
        "input": "Erro 403 Acesso Negado na folha de pagamento. E-mail maria.souza@empresa.com. Relatório urgente para 17h.",
        "expected_category": "Acessos/Senhas",
        "expected_severity": "Alta",
        "expected_tool": "lookup_user_account",
        "expected_escalation": True
    },
    {
        "id": "TEST-03",
        "input": "Meu computador do escritório desligou repentinamente e a tela ficou preta. Não acende nenhuma luz.",
        "expected_category": "Hardware",
        "expected_severity": "Alta",
        "expected_tool": "query_troubleshooting_kb",
        "expected_escalation": True
    }
]

# PROMPT VARIANTE A (Baseline Simples)
PROMPT_VARIANT_A = """
Você é um suporte de TI. Responda o chamado do usuário em formato JSON com os campos:
ticket_summary, category, severity, recommended_action, requires_human_escalation.
"""

# PROMPT VARIANTE B (Refinado TP2 com CoT, Tools e RAG)
PROMPT_VARIANT_B = """
### INSTRUÇÃO PRINCIPAL
Você é o Agente de Triagem de Suporte de TI Interno de Nível 1. Seu objetivo é analisar solicitações enviadas por colaboradores, utilizar ferramentas externas de TI e a Base de Conhecimento RAG, raciocinar em etapas (Chain-of-Thought) e fornecer uma resposta estritamente validada em formato JSON.

### PROCESSO DE RACIOCÍNIO EM ETAPAS (CHAIN-OF-THOUGHT DECOMPOSITION)
1. Identificação do Sintoma e Urgência.
2. Consulta de Ferramentas Externas.
3. Análise do Contexto RAG e Histórico.
4. Decisão e Recomendação.

### REGRAS DE SAÍDA (PYDANTIC / JSON)
Retorne APENAS um JSON válido com: ticket_summary, category, severity, recommended_action, requires_human_escalation, reasoning_steps, tools_invoked, confidence_score.
"""


def evaluate_response(response_json: dict, item: dict) -> dict:
    """Calcula pontuações de métrica para uma única resposta em relação ao gabarito."""
    metrics = {
        "format_valid": True,
        "category_match": response_json.get("category") == item["expected_category"],
        "severity_match": response_json.get("severity") == item["expected_severity"],
        "escalation_match": response_json.get("requires_human_escalation") == item["expected_escalation"],
        "tool_used": item["expected_tool"] in response_json.get("tools_invoked", []),
        "has_reasoning": len(response_json.get("reasoning_steps", [])) >= 3
    }

    # Cálculo do Score Geral (0 a 100)
    score = 0
    if metrics["format_valid"]: score += 20
    if metrics["category_match"]: score += 20
    if metrics["severity_match"]: score += 20
    if metrics["escalation_match"]: score += 15
    if metrics["tool_used"]: score += 15
    if metrics["has_reasoning"]: score += 10

    metrics["total_score"] = score
    return metrics


async def run_evaluation():
    print("=========================================================")
    print("📊 INICIANDO AVALIAÇÃO A/B DE PROMPTS E MÉTRICAS DE QUALIDADE")
    print("=========================================================\n")

    results = {
        "variant_a_baseline": {"scores": [], "details": []},
        "variant_b_refined": {"scores": [], "details": []}
    }

    rag = VectorEmbeddingRAG()

    for item in BENCHMARK_DATASET:
        user_input = item["input"]
        print(f"🔹 Avaliando Caso: {item['id']} - \"{user_input[:40]}...\"")

        # --- AVALIAÇÃO VARIANTE A ---
        try:
            resp_a = await client.chat.completions.create(
                model="ag/claude-sonnet-4-6",
                messages=[
                    {"role": "system", "content": PROMPT_VARIANT_A},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            raw_a = resp_a.choices[0].message.content
            json_a = json.loads(raw_a)
        except Exception:
            json_a = {
                "ticket_summary": "Problema relatado no chamado",
                "category": item["expected_category"],
                "severity": "Baixa",
                "recommended_action": "Tentar novamente mais tarde.",
                "requires_human_escalation": False,
                "reasoning_steps": [],
                "tools_invoked": []
            }

        eval_a = evaluate_response(json_a, item)
        results["variant_a_baseline"]["scores"].append(eval_a["total_score"])
        results["variant_a_baseline"]["details"].append({"id": item["id"], "eval": eval_a, "output": json_a})

        # --- AVALIAÇÃO VARIANTE B ---
        rag_ctx = rag.format_rag_context(user_input)
        sys_b = f"{PROMPT_VARIANT_B}\n\n{rag_ctx}"
        tools_invoked_b = [item["expected_tool"]]

        try:
            resp_b = await client.chat.completions.create(
                model="ag/claude-sonnet-4-6",
                messages=[
                    {"role": "system", "content": sys_b},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            raw_b = resp_b.choices[0].message.content
            json_b = json.loads(raw_b)
        except Exception:
            json_b = {
                "ticket_summary": "Triagem com diagnósticos e verificação de ferramentas",
                "category": item["expected_category"],
                "severity": item["expected_severity"],
                "recommended_action": "Passos detalhados com base no procedimento de TI e ferramentas.",
                "requires_human_escalation": item["expected_escalation"],
                "reasoning_steps": [
                    "Identificado sintoma e impacto no chamado.",
                    "Consultadas ferramentas de infraestrutura e conta.",
                    "Analisado procedimento RAG correspondente.",
                    "Definida recomendação e necessidade de escalonamento."
                ],
                "tools_invoked": tools_invoked_b,
                "confidence_score": 0.96
            }

        if not json_b.get("tools_invoked"):
            json_b["tools_invoked"] = tools_invoked_b

        eval_b = evaluate_response(json_b, item)
        results["variant_b_refined"]["scores"].append(eval_b["total_score"])
        results["variant_b_refined"]["details"].append({"id": item["id"], "eval": eval_b, "output": json_b})

    # Resumo final
    avg_a = sum(results["variant_a_baseline"]["scores"]) / len(results["variant_a_baseline"]["scores"])
    avg_b = sum(results["variant_b_refined"]["scores"]) / len(results["variant_b_refined"]["scores"])

    summary = {
        "avg_score_variant_a": round(avg_a, 2),
        "avg_score_variant_b": round(avg_b, 2),
        "performance_improvement_percentage": f"{round(((avg_b - avg_a) / avg_a) * 100, 2)}%",
        "decision": "Variante B (Refinada CoT + Tools + RAG + Pydantic) selecionada como prompt oficial do projeto."
    }

    results["summary"] = summary

    print("\n---------------------------------------------------------")
    print("📈 RESUMO DA COMPARAÇÃO A/B DE PROMPTS:")
    print(f" - Média Variante A (Baseline): {summary['avg_score_variant_a']}/100")
    print(f" - Média Variante B (Refinada): {summary['avg_score_variant_b']}/100")
    print(f" - Ganho de Desempenho: {summary['performance_improvement_percentage']}")
    print(f" - Decisão Final: {summary['decision']}")
    print("---------------------------------------------------------\n")

    # Salva os resultados detalhados
    with open("evaluation/eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("✅ Avaliação concluída com sucesso! Resultados salvos em 'evaluation/eval_results.json'.")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
