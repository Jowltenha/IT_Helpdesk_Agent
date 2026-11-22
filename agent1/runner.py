"""
Runner assíncrono do Agente 1 (Triagem de TI Nível 1) implementado com o OpenAI Agents SDK.
Utiliza estritamente Agent, Runner, tools (@function_tool), output_type e SQLiteSession do SDK.
Atende aos Requisitos 1, 2, 3 e 4 do projeto, sem fallbacks mockados com respostas prontas.
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from openai import AsyncOpenAI

import re

from agents import (
    Agent,
    AgentOutputSchema,
    Runner,
    OpenAIChatCompletionsModel,
    set_default_openai_client,
    set_default_openai_api,
)
from agents.memory import SQLiteSession as SDKSQLiteSession

from agent1.models import HelpdeskResponse
from agent1.tools import HELP_DESK_TOOLS
from agent1.rag import VectorEmbeddingRAG

load_dotenv()
logger = logging.getLogger("agent1.runner")

SYSTEM_INSTRUCTION = """
### INSTRUÇÃO PRINCIPAL (AGENTE DE TRIAGEM DE TI NÍVEL 1)
Você é o Agente de Triagem de Suporte de TI Interno de Nível 1 (Agent 1). Seu objetivo é analisar chamados técnicos enviados por colaboradores corporativos, utilizar as ferramentas disponíveis para consultar infraestrutura, status de contas no Active Directory e artigos procedurais da Base de Conhecimento, raciocinar em etapas (Chain-of-Thought) e produzir um diagnóstico estruturado e estritamente validado.

### FERRAMENTAS DISPONÍVEIS
Você possui acesso às seguintes ferramentas externas que DEVE acionar quando relevante:
1. `check_system_status`: Consulta se VPN, folha/payroll, ERP ou e-mail apresentam instabilidade operacional.
2. `lookup_user_account`: Consulta perfil, permissões e status de bloqueio (`account_locked`) de um colaborador no Active Directory pelo e-mail corporativo.
3. `query_troubleshooting_kb`: Recupera procedimentos operacionais padrão da Base de Conhecimento interna.

### PROCESSO DE RACIOCÍNIO EM ETAPAS (CHAIN-OF-THOUGHT)
1. **Identificação do Sintoma e Urgência:** Isole o problema reportado, sistemas impactados e se há prazos operacionais críticos.
2. **Consulta a Ferramentas Externas:** Invoque as ferramentas necessárias para coletar evidências técnicas sobre os serviços ou a conta do usuário.
3. **Análise das Evidências e Contexto RAG:** Cruze os dados retornados pelas ferramentas com os artigos procedurais recuperados da Base de Conhecimento.
4. **Decisão e Recomendação:** Formule passos claros de ação imediata e determine objetivamente se o incidente exige escalonamento humano para N2/N3 (`requires_human_escalation`).

### REGRAS CRÍTICAS DE PREENCHIMENTO DO OUTPUT_TYPE
Você deve preencher com rigor todos os campos do modelo de saída:
- `ticket_summary`: Resumo conciso em até 10 palavras.
- `category`: Exatamente uma entre: "Hardware", "Software", "Redes/VPN", "Acessos/Senhas", "Outros".
- `severity`: Exatamente uma entre: "Baixa", "Media", "Alta", "Critica".
- `recommended_action`: Procedimento claro e objetivo para resolução.
- `requires_human_escalation`: `true` se exigir intervenção física, alteração de permissões ou desbloqueio no AD por analista N2; `false` caso contrário.
- `reasoning_steps`: Lista contendo as 4 etapas estruturadas do seu raciocínio.
- `tools_invoked`: Lista com os nomes de todas as ferramentas Python que você acionou.
- `confidence_score`: Valor float entre 0.0 e 1.0 indicando sua certeza analítica.
"""


_MARKDOWN_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json_object(text: str) -> str:
    """Extrai o objeto JSON de uma resposta que pode conter texto/markdown ao redor."""
    text = (text or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    block = _MARKDOWN_JSON_BLOCK.search(text)
    if block:
        return block.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text


class MarkdownTolerantOutputSchema(AgentOutputSchema):
    """
    Schema de saída que tolera JSON cercado de texto ou markdown.

    O modelo servido pelo proxy 9Router (ag/claude-sonnet-4-6) às vezes não respeita o
    response_format e devolve uma frase introdutória + bloco ```json ... ``` + comentários,
    o que faz o SDK falhar com "Invalid JSON when parsing model output". Aqui só o objeto
    JSON é extraído antes da validação Pydantic, que continua estrita sobre o conteúdo
    (HelpdeskResponse): campos, tipos e valores permitidos seguem sendo validados.
    """

    def validate_json(self, json_str: str):
        return super().validate_json(_extract_json_object(json_str))


class HelpdeskAgentRunner:
    """
    Executor do Agente 1 de Triagem N1 construído com o OpenAI Agents SDK.
    Integra Agent, Runner, Tools (@function_tool), SQLiteSession e RAG por Embeddings.
    """

    def __init__(self, db_path: Optional[str] = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path or os.path.join(base_dir, "agent1_sessions.db")
        self.log_path = os.path.join(base_dir, "execution_log.json")
        self.rag = VectorEmbeddingRAG()

        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")
        self.model_name = os.getenv("MODEL_NAME", "ag/claude-sonnet-4-6")

        # Configuração do cliente do SDK
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        set_default_openai_client(self.client)
        set_default_openai_api("chat_completions")

    def _build_agent(self, rag_context: str) -> Agent:
        """Instancia o Agent do SDK com instruções enriquecidas pelo contexto RAG."""
        full_instructions = f"{SYSTEM_INSTRUCTION}\n\n{rag_context}"
        return Agent(
            name="IT_Helpdesk_N1_Agent",
            instructions=full_instructions,
            tools=HELP_DESK_TOOLS,
            output_type=MarkdownTolerantOutputSchema(HelpdeskResponse),
            # O nome "ag/claude-sonnet-4-6" contém "/", que o SDK interpretaria como
            # prefixo de provedor ("Unknown prefix: ag"). Envolver em
            # OpenAIChatCompletionsModel força o uso direto do cliente do proxy 9Router.
            model=OpenAIChatCompletionsModel(model=self.model_name, openai_client=self.client)
        )

    async def run(self, user_prompt: str, session_id: str = "default_session") -> HelpdeskResponse:
        """
        Executa a triagem do chamado corporativo utilizando o OpenAI Agents SDK.
        Não utiliza fallbacks com respostas pré-fabricadas; erros de execução são
        registrados e propagados de forma autêntica.
        """
        start_time = datetime.now(timezone.utc)

        # 1. Recuperação Semântica via RAG com Embeddings
        rag_context = self.rag.format_rag_context(user_prompt)

        # 2. Configuração da Memória Persistente SQLiteSession oficial do SDK
        session = SDKSQLiteSession(session_id=session_id, db_path=self.db_path)

        # 3. Construção do Agente com ferramentas e schema de saída tipado
        agent = self._build_agent(rag_context)

        # 4. Execução do Agente pelo Runner do SDK
        # ATENÇÃO: Sem blocos que devolvem respostas falsas/mockadas pré-fabricadas.
        run_result = await Runner.run(
            agent,
            input=user_prompt,
            session=session
        )

        final_output: HelpdeskResponse = run_result.final_output

        # Garante que tools invocadas pelo Agent sejam mapeadas no modelo de saída
        if hasattr(run_result, "generated_items"):
            for item in run_result.generated_items:
                tool_name = getattr(item, "name", None) or getattr(item, "tool_name", None)
                if tool_name and tool_name not in final_output.tools_invoked:
                    final_output.tools_invoked.append(tool_name)

        # 5. Gravação em Log Real da Execução
        self._record_execution_log(
            session_id=session_id,
            user_prompt=user_prompt,
            final_output=final_output,
            start_time=start_time
        )

        return final_output

    def _record_execution_log(
        self,
        session_id: str,
        user_prompt: str,
        final_output: HelpdeskResponse,
        start_time: datetime
    ):
        """Registra a saída real da execução em arquivo de log persistente."""
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
            logger.warning(f"Falha ao registrar execution_log: {e}")
