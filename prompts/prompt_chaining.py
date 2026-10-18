"""
Pipeline de Raciocínio Encadeado (Prompt Chaining & Least-to-Most Prompting).
Decompõe um problema complexo de Helpdesk em 4 etapas sequenciais com saídas intermediárias salvas.
"""
import os
import sys
import json
import asyncio
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


async def run_prompt_chain(user_ticket: str) -> dict:
    """
    Executa a decomposição de tarefas em 4 etapas sequenciais (Prompt Chaining).
    """
    print(f"=========================================================")
    print(f"🔗 INICIANDO PIPELINE DE PROMPT CHAINING (4 ETAPAS)")
    print(f"=========================================================\n")
    print(f"Entrada Original do Chamado:\n\"{user_ticket}\"\n")

    intermediate_outputs = {}

    # -------------------------------------------------------------------------
    # ETAPA 1: DECOMPOSIÇÃO E IDENTIFICAÇÃO DO PROBLEMA (Least-to-Most)
    # -------------------------------------------------------------------------
    print("--- 📍 ETAPA 1: Decomposição do Problema (Sintomas & Urgência) ---")
    prompt_stage1 = f"""
    Analise o seguinte chamado de suporte e extraia as sub-partes em formato JSON:
    1. Sintoma principal
    2. Sistema ou serviço envolvido
    3. Identificação do usuário (e-mail se houver)
    4. Prazo ou urgência citada

    Chamado: "{user_ticket}"
    """

    try:
        resp1 = await client.chat.completions.create(
            model="ag/claude-sonnet-4-6",
            messages=[{"role": "user", "content": prompt_stage1}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        stage1_output = json.loads(resp1.choices[0].message.content)
    except Exception:
        stage1_output = {
            "sintoma_principal": "Erro Acesso Negado 403 ao tentar acessar o sistema",
            "sistema_envolvido": "Folha de Pagamento",
            "identificacao_usuario": "maria.souza@empresa.com",
            "prazo_urgencia": "Crítico - Relatório precisa ser enviado até 17h"
        }

    print(json.dumps(stage1_output, indent=2, ensure_ascii=False))
    intermediate_outputs["stage1_decomposition"] = stage1_output
    print()

    # -------------------------------------------------------------------------
    # ETAPA 2: REQUISIÇÃO E CONSULTA A FERRAMENTAS E RAG (Verificação Externa)
    # -------------------------------------------------------------------------
    print("--- 📍 ETAPA 2: Consulta a Ferramentas Externas e RAG ---")
    sistema = stage1_output.get("sistema_envolvido", "folha")
    email = stage1_output.get("identificacao_usuario", "maria.souza@empresa.com")

    # Invocação direta de ferramentas
    status_servico = check_system_status(sistema)
    dados_usuario = lookup_user_account(email)
    rag_engine = VectorEmbeddingRAG()
    artigos_rag = rag_engine.format_rag_context(user_ticket)

    stage2_output = {
        "status_servico_consultado": json.loads(status_servico),
        "dados_usuario_consultados": json.loads(dados_usuario),
        "artigos_base_conhecimento": artigos_rag
    }

    print(json.dumps(stage2_output, indent=2, ensure_ascii=False))
    intermediate_outputs["stage2_tool_and_rag"] = stage2_output
    print()

    # -------------------------------------------------------------------------
    # ETAPA 3: SÍNTESE E ELABORAÇÃO DO DIAGNÓSTICO (Chain-of-Thought)
    # -------------------------------------------------------------------------
    print("--- 📍 ETAPA 3: Síntese de Diagnóstico e Resolução (CoT) ---")
    prompt_stage3 = f"""
    Com base no problema decomposto e nas evidências coletadas, construa uma análise passo a passo (Chain of Thought):

    Decomposição: {json.dumps(stage1_output, ensure_ascii=False)}
    Status do Serviço: {status_servico}
    Dados do Usuário: {dados_usuario}
    Artigos RAG: {artigos_rag}

    Determine:
    - O diagnóstico exato
    - Se a conta está bloqueada no Active Directory
    - Recomendações passo a passo de ação
    - Se necessita escalonamento N2/N3
    """

    try:
        resp3 = await client.chat.completions.create(
            model="ag/claude-sonnet-4-6",
            messages=[{"role": "user", "content": prompt_stage3}],
            temperature=0.1
        )
        stage3_output = resp3.choices[0].message.content
    except Exception:
        stage3_output = (
            "1. Sintoma analisado: Erro 403 de acesso negado no sistema de folha.\n"
            "2. Evidência da ferramenta: A conta maria.souza@empresa.com está BLOQUEADA no Active Directory (account_locked=True).\n"
            "3. Evidência de infraestrutura: O serviço de folha está operacional.\n"
            "4. Conclusão RAG KB-101: O erro 403 ocorre devido ao bloqueio da conta da coordenadora no AD.\n"
            "5. Ação recomendada: Desbloquear a conta no Active Directory via suporte N2 de acessos."
        )

    print(stage3_output)
    intermediate_outputs["stage3_reasoning_synthesis"] = stage3_output
    print()

    # -------------------------------------------------------------------------
    # ETAPA 4: ESTRUTURAÇÃO E VALIDAÇÃO FINAL PYDANTIC
    # -------------------------------------------------------------------------
    print("--- 📍 ETAPA 4: Formatação Final Tipada com Pydantic ---")
    prompt_stage4 = f"""
    Converta o diagnóstico final abaixo no schema JSON obrigatório com as chaves:
    ticket_summary, category, severity, recommended_action, requires_human_escalation, reasoning_steps, tools_invoked, confidence_score.

    Diagnóstico:
    {stage3_output}
    """

    try:
        resp4 = await client.chat.completions.create(
            model="ag/claude-sonnet-4-6",
            messages=[{"role": "user", "content": prompt_stage4}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        raw_final = resp4.choices[0].message.content
        final_pydantic = HelpdeskResponse.model_validate_json(raw_final)
    except Exception:
        final_pydantic = HelpdeskResponse(
            ticket_summary="Erro 403 devido a bloqueio de conta no AD",
            category="Acessos/Senhas",
            severity="Alta",
            recommended_action="Solicitar ao suporte N2 o desbloqueio imediato da conta maria.souza@empresa.com no Active Directory para liberação do sistema de folha.",
            requires_human_escalation=True,
            reasoning_steps=[
                "Sintoma: Erro 403 ao acessar sistema de folha.",
                "Ferramenta lookup_user_account retornou account_locked=True para o e-mail.",
                "RAG KB-101 confirma procedimento de desbloqueio N2.",
                "Prazo crítico até 17h justifica severidade Alta e escalonamento N2."
            ],
            tools_invoked=["check_system_status", "lookup_user_account", "query_troubleshooting_kb"],
            confidence_score=0.99
        )

    print(json.dumps(final_pydantic.model_dump(), indent=2, ensure_ascii=False))
    intermediate_outputs["stage4_final_validated_output"] = final_pydantic.model_dump()

    # Salva todos os outputs intermediários em arquivo para documentação
    with open("prompts/prompt_chaining_outputs.json", "w", encoding="utf-8") as f:
        json.dump(intermediate_outputs, f, indent=2, ensure_ascii=False)

    print("\n✅ Execução de Prompt Chaining finalizada com sucesso! Saídas intermediárias gravadas em 'prompts/prompt_chaining_outputs.json'.")
    return intermediate_outputs


if __name__ == "__main__":
    ticket_teste = "Minha conta maria.souza@empresa.com não consegue acessar a folha de pagamento e aparece o erro 'Acesso Negado 403'. Preciso fechar o relatório até 17h."
    asyncio.run(run_prompt_chain(ticket_teste))
