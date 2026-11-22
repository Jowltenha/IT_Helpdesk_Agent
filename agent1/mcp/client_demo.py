"""
Demonstração da integração MCP do Agente 1.

Mostra os DOIS lados do contrato:
  1. Cliente MCP "cru" (SDK `mcp`): lista as ferramentas com seus JSON Schemas (gerados dos
     modelos Pydantic) e chama cada uma, validando a resposta com o mesmo modelo Pydantic.
  2. Agente do OpenAI Agents SDK consumindo o servidor via `MCPServerStdio` — prova que
     qualquer agente compatível com MCP pode usar as ferramentas do Agente 1 sem importar
     o código Python dele.

Uso (raiz do repositório):
    python -m agent1.mcp.client_demo            # parte 1 (não usa LLM)
    python -m agent1.mcp.client_demo --agent    # parte 1 + parte 2 (usa o LLM do proxy)
Saída gravada em tests/results/mcp_integration.json.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent1.models import KBSearchResult, SystemStatus, UserAccountResult

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVER = StdioServerParameters(command=sys.executable, args=["-m", "agent1.mcp.server"], cwd=ROOT)

CALLS = [
    ("check_system_status", {"service_name": "sap"}, SystemStatus),
    ("lookup_user_account", {"user_email": "maria.souza@empresa.com."}, UserAccountResult),
    ("lookup_user_account", {"user_email": "invasor@gmail.com"}, UserAccountResult),
    ("query_troubleshooting_kb", {"query": "esqueci minha senha do outlook", "top_k": 1}, KBSearchResult),
]


async def raw_client() -> dict:
    out = {"tools": [], "calls": []}
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            out["server"] = {"name": init.serverInfo.name, "protocol": init.protocolVersion}
            for t in (await session.list_tools()).tools:
                out["tools"].append({"name": t.name, "read_only": t.annotations.readOnlyHint,
                                     "input_schema": t.inputSchema, "output_schema": t.outputSchema})
            for name, args, model in CALLS:
                res = await session.call_tool(name, args)
                validated = model.model_validate(res.structuredContent)  # contrato de saída
                out["calls"].append({"tool": name, "arguments": args, "is_error": res.isError,
                                     "validated_output": validated.model_dump()})
                print(f"✔ {name}({args}) -> {validated.model_dump_json()[:160]}")
            bad = await session.call_tool("lookup_user_account", {"user_email": "x"})
            out["calls"].append({"tool": "lookup_user_account", "arguments": {"user_email": "x"},
                                 "is_error": bad.isError, "error": bad.content[0].text[:300]})
            print(f"✔ entrada inválida rejeitada pelo schema Pydantic: isError={bad.isError}")
    return out


async def sdk_agent() -> dict:
    from openai import AsyncOpenAI
    from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
    from agents.mcp import MCPServerStdio
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
    set_tracing_disabled(True)
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
    model = OpenAIChatCompletionsModel(model=os.getenv("MODEL_NAME", "ag/claude-sonnet-4-6"), openai_client=client)
    async with MCPServerStdio(name="helpdesk-agent1-tools",
                              params={"command": sys.executable, "args": ["-m", "agent1.mcp.server"], "cwd": ROOT},
                              cache_tools_list=True, client_session_timeout_seconds=30) as server:
        agent = Agent(name="MCP_Consumer_Demo", model=model, mcp_servers=[server],
                      instructions="Use as ferramentas MCP para responder em uma frase, em português.")
        q = "A conta maria.souza@empresa.com está bloqueada? E a VPN está operacional?"
        result = await Runner.run(agent, q, max_turns=6)
        tools = [i.raw_item.name for i in result.new_items if i.type == "tool_call_item"]
        print(f"✔ Agente SDK via MCP chamou {tools}: {result.final_output}")
        return {"question": q, "tools_called": tools, "answer": result.final_output}


async def main():
    report = {"executed_at": datetime.now(timezone.utc).isoformat(), "raw_client": await raw_client()}
    if "--agent" in sys.argv:
        report["agents_sdk_consumer"] = await sdk_agent()
    path = os.path.join(ROOT, "tests", "results", "mcp_integration.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("salvo em", path)


if __name__ == "__main__":
    asyncio.run(main())
