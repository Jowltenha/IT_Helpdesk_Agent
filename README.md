# Agente de Triagem de TI - Helpdesk Interno (TP2)

Este repositório contém a implementação evoluída do **Agente de IA de Triagem de Suporte Técnico de Nível 1**, desenvolvido para o **Projeto de Bloco** (TP2).

O projeto atende **estritamente a todos os 7 entregáveis exigidos pelo professor** (ver imagem de diretrizes do slide e `RELATORIO_TECNICO.md`):

1. **Gatilho de Entrada (Trigger / n8n):** Webhook de Chatbot / Aplicativo Web / Telegram / Gmail.
2. **Fonte de Informações (Estruturada e Não Estruturada):** APIs de Status e Active Directory (JSON) + Banco SQLite + Artigos de KB/SOPs em texto livre via RAG.
3. **Diagrama de Arquitetura dos 9 Componentes:** Mapeamento em camadas de 1 a 9.
4. **Descrição Textual da Arquitetura:** Detalhamento do papel dos 9 componentes.
5. **Exemplo de Fluxo de Dados:** Rastreamento passo a passo da mensagem até o retorno validado.
6. **Dado Estruturado (DB / API):** Mapeamento de tabelas SQLite e esquemas JSON.
7. **Demais Itens do TP2:** Tools Python `@function_tool`, raciocínio encadeado (*Prompt Chaining* / *CoT*), memória persistente, RAG, validação Pydantic v2 e benchmark A/B.

---

## 📁 Estrutura do Repositório

```text
IT_Helpdesk_Agent/
├── agent/                         # Código-fonte principal do Agente
│   ├── __init__.py
│   ├── main.py                    # Runner principal do Agente com Tools, SQLiteSession, RAG e Pydantic
│   ├── tools.py                   # Ferramentas Python externas (@function_tool)
│   ├── memory.py                  # Gerenciador de memória de sessão SQLite (SQLiteSession)
│   ├── rag.py                     # Engine RAG de busca semântica por embeddings
│   ├── models.py                  # Schemas Pydantic (HelpdeskResponse, UserPermission, etc.)
│   ├── execution_log.json         # Registro de execuções com saídas tipadas
│   └── requirements.txt           # Dependências Python atualizadas
├── prompts/                       # Documentação de Prompts e Raciocínio Encadeado
│   ├── prompt_helpdesk.md         # Documentação da anatomia do prompt principal
│   ├── prompt_chaining.py         # Script do pipeline de raciocínio encadeado (4 etapas)
│   ├── prompt_chaining_outputs.json # Saídas intermediárias gravadas de cada etapa
│   └── prompts_chained_doc.md     # Documentação detalhada dos prompts encadeados
├── evaluation/                    # Avaliação Automatizada e Métricas de Qualidade
│   ├── evaluate.py                # Benchmark automatizado A/B (Variante A vs Variante B)
│   ├── eval_results.json          # Resultados gravados do benchmark A/B
│   └── reflection_log.md          # Registro do ciclo Prompt-Response-Reflect-Revise
├── spec/
│   └── especificacao_projeto.md   # Especificação e diagrama de arquitetura dos 9 componentes
├── RELATORIO_TECNICO.md           # Relatório Técnico Completo do TP2 (Mapeamento dos 7 entregáveis)
├── README.md                      # Instruções de uso e visão geral do repositório
└── pyproject.toml                 # Configuração do projeto Python
```

---

## ⚙️ Como Executar o Projeto Localmente

```bash
# 1. Ativar o ambiente virtual
source .venv/bin/activate

# 2. Executar o Agente Principal (Main Runner com Tools, Memory, RAG e Pydantic):
python agent/main.py

# 3. Executar o Pipeline de Prompt Chaining (Decomposição em 4 Etapas):
python prompts/prompt_chaining.py

# 4. Executar o Benchmark e Avaliação A/B de Prompts:
python evaluation/evaluate.py
```

---

## 📑 Relatório Técnico e Entregáveis

O relatório técnico completo contendo o **mapeamento oficial dos 7 entregáveis do slide do professor**, os **9 componentes da arquitetura**, a matriz de riscos e o guia para gravação do vídeo está disponível em **[`RELATORIO_TECNICO.md`](RELATORIO_TECNICO.md)**.

O agente valida a resposta e gera um JSON estruturado com o seguinte esquema:

```json
{
  "ticket_summary": "Erro 403 ao acessar sistema de folha de pagamento",
  "category": "Acessos/Senhas",
  "severity": "Alta", 
  "recommended_action": "1. Verificar se o usuário possui perfil de acesso ativo no sistema. 2. Confirmar alteração recente de permissões. 3. Solicitar ao administrador a revisão e reativação do acesso.",
  "requires_human_escalation": true
}

```

Os resultados de cada execução são salvos automaticamente no arquivo `execution_log.json`.
