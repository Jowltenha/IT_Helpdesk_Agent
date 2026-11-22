> 🔗 **Repositório GitHub:** https://github.com/Jowltenha/IT_Helpdesk_Agent

# TOOLS.md: Ferramentas do Agente 1 (Triagem N1)

> Contrato formal de entrada e saída de **cada ferramenta do Agente 1**.
> Os schemas são modelos Pydantic v2 em [`models.py`](models.py) (saída) e [`mcp/server.py`](mcp/server.py) (entrada).
> O **mesmo contrato** atende os dois consumidores:
> - o próprio agente, via `@function_tool` em [`tools.py`](tools.py);
> - clientes externos, via o **servidor MCP**.

## Regras comuns a todas as ferramentas

| Regra | Detalhe |
| :--- | :--- |
| Somente leitura | Nenhuma ferramenta altera estado. MCP: `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`. |
| Hook `PreToolUse` | Toda chamada passa por `pre_tool_use_hook()` antes de executar. Ele valida, sanitiza e grava `hooks/hook_audit.log` (JSON Lines com `timestamp`, `tool_name`, `arguments`, `allowed`, `reason`). |
| Negação explícita | Se o hook negar, a ferramenta **não lança exceção**: devolve `status="NEGADO_PELO_HOOK"` e o motivo, e o modelo decide o próximo passo. |
| Implementação única | `*_impl()` retorna o modelo Pydantic. O wrapper `@function_tool` serializa com `model_dump_json()`, e o MCP devolve o modelo como `structuredContent`. |
| Dados | Monitoria e AD são **simulados** (dicionários em `tools.py`), porque o ambiente acadêmico não tem AD real. A KB usa **embeddings reais**. |

---

## 1. `check_system_status`

Consulta o status operacional de um serviço corporativo monitorado.

**Entrada** (`CheckSystemStatusInput`):

| Campo | Tipo | Obrigatório | Restrições |
| :--- | :--- | :-: | :--- |
| `service_name` | string | sim | 2–40 caracteres; sem `; < > & \| \` $ \\`. Chaves: `vpn`, `folha`, `email`, `erp`. Sinônimos aceitos: `sap`→erp, `outlook`/`exchange`/`office 365`→email, `folha de pagamento`/`payroll`/`rh`→folha, `openvpn`/`gateway`/`acesso remoto`→vpn. |

**Saída** (`SystemStatus`):

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `service_key` | string \| null | chave canônica resolvida (`vpn`, `folha`, `email`, `erp`) |
| `service_name` | string | nome do serviço |
| `status` | enum | `Operational` · `Degradado` · `Indisponivel` · `Manutencao` · `Desconhecido` · `NEGADO_PELO_HOOK` |
| `message` | string | detalhe oficial |
| `last_updated` | string | timestamp da verificação, ou `N/A` |
| `monitored_services` | string[] | preenchido quando o serviço é `Desconhecido` ou negado, para o modelo se autocorrigir |

**Exemplos:**
```json
// in
{"service_name": "sap"}
// out
{"service_key":"erp","service_name":"ERP SAP Corporativo","status":"Manutencao","message":"Janela de manutencao programada para atualizacao de patches ate 14h.","last_updated":"2026-10-02 08:00:00","monitored_services":[]}

// in
{"service_name": "infraestrutura"}
// out
{"service_key":null,"service_name":"infraestrutura","status":"Desconhecido","message":"Servico nao monitorado. Use uma das chaves em monitored_services ou siga sem esta consulta.","last_updated":"N/A","monitored_services":["email","erp","folha","vpn"]}

// in
{"service_name": "vpn; rm -rf /"}
// out
{"status":"NEGADO_PELO_HOOK","message":"Bloqueado: nome de serviço 'vpn; rm -rf /' contém caracteres de injeção.", ...}
```

## 2. `lookup_user_account`

Consulta perfil, grupos e bloqueio de um colaborador no Active Directory.

**Entrada** (`LookupUserAccountInput`):

| Campo | Tipo | Obrigatório | Restrições |
| :--- | :--- | :-: | :--- |
| `user_email` | string | sim | 6–120 caracteres; precisa terminar em `@empresa.com`; sem metacaracteres. É normalizado: minúsculas, sem espaços, sem pontuação final (`maria.souza@empresa.com.` → `maria.souza@empresa.com`). |

**Saída** (`UserAccountResult`):

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `email` | string | e-mail normalizado |
| `found` | bool | a conta existe no AD |
| `status` | enum | `ENCONTRADO` · `NAO_ENCONTRADO` · `NEGADO_PELO_HOOK` |
| `name`, `role` | string \| null | dados do colaborador |
| `groups` | string[] | grupos do AD (ex.: `Folha_Pagamento_Admin`, `VPN_Users`) |
| `account_locked` | bool \| **null** | `true`/`false` se a conta foi consultada; **`null` se não foi possível consultar**. Antes do TP5 o valor era `false`, o que sugeria uma conta saudável. |
| `message` | string | orientação (ex.: "Encaminhar para RH/Onboarding; nao solicitar desbloqueio.") |

**Exemplos:**
```json
// in
{"user_email":"Maria.Souza@empresa.com."}
// out
{"email":"maria.souza@empresa.com","found":true,"status":"ENCONTRADO","name":"Maria Souza","role":"Coordenadora de RH","groups":["RH_Gestao","Folha_Pagamento_Admin","VPN_Users"],"account_locked":true,"message":"Conta localizada."}

// in
{"user_email":"fulano@gmail.com"}
// out
{"email":"fulano@gmail.com","found":false,"status":"NEGADO_PELO_HOOK","account_locked":null,"message":"Bloqueado: e-mail 'fulano@gmail.com' inválido ou fora do domínio corporativo '@empresa.com'. Peça ao colaborador o e-mail corporativo; nao assuma o estado da conta.", ...}
```

## 3. `query_troubleshooting_kb`

Busca semântica nos procedimentos da Base de Conhecimento (KB-101 a KB-104).

**Entrada** (`QueryKBInput`):

| Campo | Tipo | Obrigatório | Restrições |
| :--- | :--- | :-: | :--- |
| `query` | string | sim | 2–300 caracteres; metacaracteres removidos pelo hook |
| `top_k` | int | não (padrão 2) | 1–4. Disponível no MCP; no `@function_tool` o valor é fixo em 2. |

**Saída** (`KBSearchResult`):

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `query` | string | consulta efetivamente executada |
| `status` | enum | `ENCONTRADO` · `SEM_ARTIGO_RELEVANTE` · `KB_INDISPONIVEL` · `NEGADO_PELO_HOOK` |
| `articles[]` | `KnowledgeArticle` | `article_id`, `title`, `category`, `solution`, `relevance_score` (0–1) |
| `min_similarity` | float | limiar aplicado (`RAG_MIN_SIMILARITY`, padrão 0.62) |
| `message` | string | orientação (ex.: "Nenhum artigo relevante; nao cite IDs de artigo no laudo.") |

**Algoritmo:**
- embedding da consulta com `gemini-embedding-001` (1536 dimensões) via `POST /v1/embeddings` do proxy;
- similaridade de cosseno com os 4 artigos, indexados uma vez por processo;
- retorna o top-k com score ≥ limiar.

**Calibração do limiar** ([`tests/results/rag_calibration.json`](../tests/results/rag_calibration.json)):
- 7 consultas relevantes ficaram entre 0.643 e 0.778, todas com o artigo certo em 1º lugar;
- 5 consultas irrelevantes ficaram ≤ 0.593;
- limiar adotado: 0.62.

**Exemplo:**
```json
// in
{"query":"esqueci minha senha do outlook","top_k":1}
// out
{"query":"esqueci minha senha do outlook","status":"ENCONTRADO","articles":[{"article_id":"KB-104","title":"Política de Redefinição de Senha e Desbloqueio de E-mail Corporativo","category":"Acessos/Senhas","solution":"Para redefinição de senha do Outlook/Office 365: 1. ...","relevance_score":0.735}],"min_similarity":0.62,"message":""}
```

---

## 4. Hook `PreToolUse`: regras por ferramenta

| Ferramenta | Nega quando | Sanitiza |
| :--- | :--- | :--- |
| `lookup_user_account` | e-mail vazio; contém `; < > & \| \` $ \\`; sintaxe inválida; domínio diferente de `@empresa.com` | minúsculas, `strip`, remove pontuação final |
| `check_system_status` | contém metacaracteres; vazio ou com mais de 40 caracteres; caracteres fora de `[\w\s/.-]` | minúsculas, `strip` |
| `query_troubleshooting_kb` | menos de 2 caracteres após sanitizar | remove metacaracteres; trunca em 300 |
| qualquer outra | **sempre** (ferramenta fora da política) | — |

## 5. Servidor MCP: contrato de integração

| Item | Valor |
| :--- | :--- |
| Implementação | [`agent1/mcp/server.py`](mcp/server.py): `FastMCP` com `@mcp.tool()` e `structured_output=True` |
| Nome / versão | `helpdesk-agent1-tools` / `1.0.0` |
| Transportes | **stdio** (padrão): `python -m agent1.mcp.server` · **streamable HTTP**: `python -m agent1.mcp.server --transport streamable-http --port 8011` (endpoint `/mcp`) |
| Ferramentas | `check_system_status`, `lookup_user_account`, `query_troubleshooting_kb`, com os parâmetros das seções 1–3 como argumentos de 1º nível |
| `inputSchema` | JSON Schema gerado a partir das anotações Pydantic (`Annotated[..., Field(...)]`). Cada tool também reconstrói `CheckSystemStatusInput`, `LookupUserAccountInput` ou `QueryKBInput` para validar. Entrada inválida → `isError=true` com o erro de validação. |
| `outputSchema` | JSON Schema de `SystemStatus` / `UserAccountResult` / `KBSearchResult`. A resposta vem em `structuredContent` e também como texto JSON em `content[0]`, por compatibilidade. |
| Recurso | `helpdesk://agent1/contract` (este arquivo, em Markdown) |
| Segurança | Mesmo hook `PreToolUse` e mesma auditoria do agente. Tools somente leitura. stdio não expõe porta de rede. |
| Registro no Claude Code | `.mcp.json` / [`.mcp.example.json`](../.mcp.example.json): `{"helpdesk-agent1-tools": {"command": ".venv/bin/python", "args": ["-m","agent1.mcp.server"], "cwd": "<repo>"}}` |
| Consumo pelo Agents SDK | `MCPServerStdio(params={"command": python, "args": ["-m","agent1.mcp.server"]})` em `Agent(mcp_servers=[...])`. Ver [`mcp/client_demo.py`](mcp/client_demo.py). |
| Evidência | [`tests/results/mcp_integration.json`](../tests/results/mcp_integration.json): `tools/list` com os schemas, 4 chamadas validadas com Pydantic, 1 entrada inválida rejeitada e um agente do SDK respondendo via MCP |
| Testes | `test_mcp_server_lists_tools_with_pydantic_schemas` em [`test_agent1_unit.py`](test_agent1_unit.py) |
