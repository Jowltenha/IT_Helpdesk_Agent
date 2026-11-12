"""
Agente Principal de Triagem de TI - Helpdesk Interno (TP2 / TP3)
Implementado estritamente com o OpenAI Agents SDK:
 - Agent, Runner e tools (@function_tool)
 - Memória persistente oficial com SQLiteSession
 - Recuperação semântica RAG por Embeddings
 - Saída tipada e validada via Pydantic (output_type=HelpdeskResponse)
 - Sem fallbacks mockados com respostas prontas
"""
import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Garante raiz no path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents import Agent, Runner, set_default_openai_client, set_default_openai_api
from agents.memory import SQLiteSession as SDKSQLiteSession

from agent.models import HelpdeskResponse
from agent.tools import HELP_DESK_TOOLS
from agent.rag import VectorEmbeddingRAG

load_dotenv()

SYSTEM_INSTRUCTION = """
### INSTRUÇÃO PRINCIPAL (AGENTE DE TRIAGEM DE TI NÍVEL 1)
Você é o Agente de Triagem de Suporte de TI Interno de Nível 1. Seu objetivo é analisar solicitações enviadas por colaboradores corporativos, utilizar as ferramentas para consultar dados de infraestrutura, Active Directory e a Base de Conhecimento RAG, raciocinar em etapas (Chain-of-Thought) e fornecer uma resposta estritamente validada no formato do schema.

### PROCESSO DE RACIOCÍNIO EM ETAPAS (CHAIN-OF-THOUGHT)
Siga obrigatoriamente estes passos no seu raciocínio:
1. **Identificação do Sintoma e Urgência:** Identifique o problema relatado, o sistema afetado e se há prazos operacionais envolvidos.
2. **Consulta de Ferramentas Externas:** Se o problema envolver sistemas (ex: VPN, Folha, ERP) ou usuários específicos, invoque a ferramenta correspondente (`check_system_status`, `lookup_user_account` ou `query_troubleshooting_kb`).
3. **Análise do Contexto RAG e Histórico:** Confronte as evidências técnicas com os procedimentos recuperados da Base de Conhecimento e histórico da sessão.
4. **Decisão e Recomendação:** Sintetize os achados, recomende a ação passo a passo e determine se exige escalonamento humano para N2/N3.
"""


class HelpdeskAgentRunner:
    """
    Orquestrador do Agente de Helpdesk de TI com Suporte a Tools, RAG, SQLiteSession e Pydantic.
    """

    def __init__(self, db_path: str = "agent_sessions.db"):
        self.db_path = db_path
        self.log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "execution_log.json")
        self.rag = VectorEmbeddingRAG()

        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
        self.model_name = os.getenv("MODEL_NAME", "ag/claude-sonnet-4-6")

        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        set_default_openai_client(self.client)
        set_default_openai_api("chat_completions")

    def _build_agent(self, rag_context: str) -> Agent:
        full_instructions = f"{SYSTEM_INSTRUCTION}\n\n{rag_context}"
        return Agent(
            name="HelpdeskN1Agent",
            instructions=full_instructions,
            tools=HELP_DESK_TOOLS,
            output_type=HelpdeskResponse,
            model=self.model_name
        )

    async def run(self, user_prompt: str, session_id: str = "default_session") -> HelpdeskResponse:
        """
        Executa uma rodada completa de triagem para uma instrução do usuário.
        Execução real sem respostas prontas simuladas.
        """
        start_time = datetime.now(timezone.utc)
        rag_context = self.rag.format_rag_context(user_prompt)
        session = SDKSQLiteSession(session_id=session_id, db_path=self.db_path)
        agent = self._build_agent(rag_context)

        run_result = await Runner.run(
            agent,
            input=user_prompt,
            session=session
        )

        final_output: HelpdeskResponse = run_result.final_output

        # Registra no execution_log real
        self._record_execution_log(session_id, user_prompt, final_output, start_time)

        return final_output

    def _record_execution_log(self, session_id: str, user_prompt: str, final_output: HelpdeskResponse, start_time: datetime):
        completed_time = datetime.now(timezone.utc)
        log_entry = {
            "timestamp": completed_time.isoformat(),
            "session_id": session_id,
            "duration_seconds": round((completed_time - start_time).total_seconds(), 3),
            "user_prompt": user_prompt,
            "output": final_output.model_dump(),
            "agent_model": self.model_name
        }
        try:
            entries = []
            if os.path.exists(self.log_path):
                with open(self.log_path, "r", encoding="utf-8") as f:
                    try:
                        entries = json.load(f)
                    except json.JSONDecodeError:
                        entries = []
            entries.append(log_entry)
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Aviso: Não foi possível salvar execution_log: {e}")


async def main():
    print("=========================================================")
    print("🤖 EXECUTANDO O AGENTE DE HELPDESK DE TI (OPENAI AGENTS SDK)")
    print("=========================================================\n")

    runner = HelpdeskAgentRunner()
    session_id = "sessao_demonstracao_sdk"

    prompt_run = "Não consigo acessar a folha de pagamento. Aparece erro 403 Acesso Negado. E-mail maria.souza@empresa.com. Urgente até 17h."
    print(f"User Input: {prompt_run}\n")

    try:
        result = await runner.run(prompt_run, session_id=session_id)
        print("--- 🎯 Saída Tipada Validada via Pydantic (output_type) ---")
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"❌ Erro na execução da inferência: {e}")
        print("Certifique-se de que o proxy local (9Router) ou sua chave OpenAI estejam ativos.")


if __name__ == "__main__":
    asyncio.run(main())
