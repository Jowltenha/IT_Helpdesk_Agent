import os
import json
import re
import asyncio
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

load_dotenv()

class HelpdeskResponse(BaseModel):
    ticket_summary: str = Field(
        description="Resumo claro e conciso do problema relatado em até 10 palavras."
    )
    category: str = Field(
        description="Categoria do chamado: Hardware, Software, Redes/VPN, Acessos/Senhas ou Outros."
    )
    severity: str = Field(
        description="Nível de severidade: Baixa, Média, Alta ou Crítica."
    )
    recommended_action: str = Field(
        description="Passos ou recomendações imediatas para a resolução do problema."
    )
    requires_human_escalation: bool = Field(
        description="True se o problema exigir intervenção presencial ou nível N2/N3 de TI."
    )

SYSTEM_INSTRUCTION = """
### INSTRUÇÃO
Você é o Agente de Triagem de Suporte de TI Interno. Seu objetivo é analisar solicitações enviadas por colaboradores, classificar a natureza do problema e fornecer orientações iniciais.

### CONTEXTO
Você opera no nível 1 do suporte técnico de uma empresa. Seu papel é agilizar a triagem antes que os chamados sejam atribuídos aos analistas.

### REGRAS DE SAÍDA (CRÍTICO)
Você DEVE retornar APENAS um objeto JSON válido cujas chaves coincidam EXATAMENTE com o schema especificado abaixo. NÃO traduza nem modifique o nome dos campos.

Campos obrigatórios do JSON:
- "ticket_summary" (string): Resumo do problema em até 10 palavras.
- "category" (string): Categoria ("Hardware", "Software", "Redes/VPN", "Acessos/Senhas", "Outros").
- "severity" (string): Severidade ("Baixa", "Média", "Alta", "Crítica").
- "recommended_action" (string): Passos recomendados.
- "requires_human_escalation" (boolean): true ou false.

Exemplo exato do formato de saída esperada:
{
  "ticket_summary": "Erro de permissão 403 ao tentar acessar a folha de pagamento",
  "category": "Acessos/Senhas",
  "severity": "Alta",
  "recommended_action": "Verificar permissões de acesso do usuário no sistema financeiro e redefinir permissões de perfil N2.",
  "requires_human_escalation": true
}
"""

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

def clean_json_string(content: str) -> str:
    """Remove blocos de código Markdown caso o modelo envie ```json ... ```"""
    content = content.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if match:
        return match.group(1).strip()
    return content

async def main():
    user_prompt = "Não consigo acessar o sistema de folha de pagamento e preciso enviar o relatório até 17h. Aparece o erro 'Acesso Negado 403'."
    
    print(f"--- Entrada do Usuário ---\n{user_prompt}\n")

    response = await client.chat.completions.create(
        model="ag/claude-sonnet-4-6",
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )

    raw_content = response.choices[0].message.content
    cleaned_json = clean_json_string(raw_content)

    # Validação do JSON com Pydantic
    final_output = HelpdeskResponse.model_validate_json(cleaned_json)

    print("--- Saída Estruturada (Pydantic / JSON) ---")
    print(json.dumps(final_output.model_dump(), indent=2, ensure_ascii=False))

    # Salva o resultado no execution_log.json
    with open("execution_log.json", "w", encoding="utf-8") as f:
        json.dump(final_output.model_dump(), f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())