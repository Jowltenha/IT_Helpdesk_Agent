# Documentação de Pipelines de Raciocínio Encadeado (Prompt Chaining & Least-to-Most)

Este documento detalha o pipeline de raciocínio encadeado (*Prompt Chaining*) e decomposição de tarefas (*Task Decomposition*) implementado no **Agente de Triagem de TI - Helpdesk Interno (TP2)**.

---

## 1. Visão Geral da Arquitetura de Decomposição

Para chamados de TI complexos — que envolvem simultaneamente sintomas de software, identificação de usuário, prazos operacionais e múltiplos sistemas —, o uso de um único prompt (*single-shot*) pode causar omissão de diagnósticos cruciais ou falhas na verificação de permissões.

Para resolver este problema, aplicamos o método **Least-to-Most Prompting** combinado com **Chain-of-Thought (CoT)**, dividindo o fluxo de resolução em 4 etapas sequenciais:

```
[Entrada do Chamado] 
       ⬇️
[Etapa 1: Decomposição Least-to-Most] ➡️ Extrai sub-problemas e entidade
       ⬇️
[Etapa 2: Execução de Tools & RAG]   ➡️ Consulta status de serviços, conta AD e KB RAG
       ⬇️
[Etapa 3: Síntese e Raciocínio CoT]   ➡️ Analisa as evidências e constrói o diagnóstico
       ⬇️
[Etapa 4: Validação Pydantic]        ➡️ Formata a saída no schema final tipado JSON
```

---

## 2. Sequência Detalhada dos Prompts e Saídas Intermediárias

### 🔹 Entrada de Teste do Chamado:
> *"Minha conta maria.souza@empresa.com não consegue acessar a folha de pagamento e aparece o erro 'Acesso Negado 403'. Preciso fechar o relatório até 17h."*

---

### 📍 Etapa 1: Decomposição do Problema (Least-to-Most Prompting)

#### Prompt da Etapa 1:
```text
Analise o seguinte chamado de suporte e extraia as sub-partes em formato JSON:
1. Sintoma principal
2. Sistema ou serviço envolvido
3. Identificação do usuário (e-mail se houver)
4. Prazo ou urgência citada

Chamado: "{user_ticket}"
```

#### Output Intermediário (Etapa 1):
```json
{
  "sintoma_principal": "Erro Acesso Negado 403 ao tentar acessar o sistema",
  "sistema_envolvido": "Folha de Pagamento",
  "identificacao_usuario": "maria.souza@empresa.com",
  "prazo_urgencia": "Crítico - Relatório precisa ser enviado até 17h"
}
```

---

### 📍 Etapa 2: Consulta a Ferramentas Externas e RAG Semântico

Nesta etapa, os parâmetros extraídos na Etapa 1 são passados programmaticamente para as ferramentas Python e para o motor RAG:

- **Tool `check_system_status("folha")`**
- **Tool `lookup_user_account("maria.souza@empresa.com")`**
- **Engine RAG KB (`VectorEmbeddingRAG`)**

#### Output Intermediário (Etapa 2):
```json
{
  "status_servico_consultado": {
    "service_name": "Sistema de Folha de Pagamento",
    "status": "Operational",
    "message": "Todos os serviços operando normalmente. Sem instabilidades registradas.",
    "last_updated": "2026-10-02 11:00:00"
  },
  "dados_usuario_consultados": {
    "email": "maria.souza@empresa.com",
    "name": "Maria Souza",
    "role": "Coordenadora de RH",
    "groups": ["RH_Gestao", "Folha_Pagamento_Admin", "VPN_Users"],
    "account_locked": true
  },
  "artigos_base_conhecimento": "--- CONTEXTO PROCEDURAL (RAG KB RETRIEVAL) ---\nArtigo ID: KB-101 | Título: Resolução de Erros de Permissão 403 e Acesso Negado em Sistemas Web (Relevância: 0.92)\nCategoria: Acessos/Senhas\nProcedimento: Para erros 403 no sistema de Folha de Pagamento ou ERP: 1. Confirmar se o usuário possui perfil ativo no AD corporativo. 2. Verificar se o grupo Folha_Pagamento_Admin ou Leitura foi atribuído. 3. Caso a conta esteja bloqueada por tentativas inválidas, acionar N2 para redefinição. 4. Limpeza de cache e cookies no navegador resolve casos de sessão corrompida."
}
```

---

### 📍 Etapa 3: Síntese de Diagnóstico e Raciocínio Chain-of-Thought (CoT)

#### Prompt da Etapa 3:
```text
Com base no problema decomposto e nas evidências coletadas, construa uma análise passo a passo (Chain of Thought):

Decomposição: {stage1_output}
Status do Serviço: {status_servico}
Dados do Usuário: {dados_usuario}
Artigos RAG: {artigos_rag}

Determine:
- O diagnóstico exato
- Se a conta está bloqueada no Active Directory
- Recomendações passo a passo de ação
- Se necessita escalonamento N2/N3
```

#### Output Intermediário (Etapa 3):
```text
1. Sintoma analisado: Erro 403 de acesso negado no sistema de folha de pagamento reportado por maria.souza@empresa.com.
2. Evidência da infraestrutura: O serviço de folha de pagamento está 100% operacional.
3. Evidência do usuário (Tool lookup_user_account): A usuária pertence ao grupo Folha_Pagamento_Admin, porém sua conta no Active Directory encontra-se BLOQUEADA (account_locked=True).
4. Evidência RAG (KB-101): Erros 403 associados a contas bloqueadas no AD exigem intervenção da equipe N2 para redefinição/desbloqueio.
5. Conclusão e Prioridade: Devido ao prazo crítico de envio do relatório até 17h, o chamado deve ser categorizado como Severidade Alta e escalado imediatamente para o N2 de Acessos.
```

---

### 📍 Etapa 4: Formatação Final Tipada com Pydantic

#### Output Intermediário (Etapa 4 - JSON Validado):
```json
{
  "ticket_summary": "Erro 403 devido a bloqueio de conta no AD",
  "category": "Acessos/Senhas",
  "severity": "Alta",
  "recommended_action": "Solicitar ao suporte N2 o desbloqueio imediato da conta maria.souza@empresa.com no Active Directory para liberação do sistema de folha de pagamento.",
  "requires_human_escalation": true,
  "reasoning_steps": [
    "Sintoma: Erro 403 ao acessar sistema de folha.",
    "Ferramenta lookup_user_account retornou account_locked=True para o e-mail.",
    "RAG KB-101 confirma procedimento de desbloqueio N2.",
    "Prazo crítico até 17h justifica severidade Alta e escalonamento N2."
  ],
  "tools_invoked": [
    "check_system_status",
    "lookup_user_account",
    "query_troubleshooting_kb"
  ],
  "confidence_score": 0.99
}
```

---

## 3. Benefícios Observados da Abordagem Encadeada

1. **Eliminação de Alucinações:** Ao separar a consulta de dados externos da geração da resposta final, o modelo trabalha exclusivamente com fatos retornados pelas ferramentas.
2. **Desbloqueio de Diagnósticos Precisos:** No teste sem ferramentas/chaining, o agente assumia genérica "falha de permissão no navegador". Com o chaining, o agente descobriu a causa raiz exata: `account_locked = True`.
3. **Auditabilidade:** Cada passo do raciocínio fica registrado para fins de compliance e melhoria contínua de suporte técnico.
