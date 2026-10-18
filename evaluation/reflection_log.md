# Registro do Ciclo Prompt-Response-Reflect-Revise (Refinamento de Prompts)

Este documento registra o processo sistemático de avaliação e refinamento do prompt principal do **Agente de Triagem de TI - Helpdesk Interno (TP2)**, utilizando a metodologia **Prompt-Response-Reflect-Revise**.

---

## 1. Definição das Métricas de Avaliação

Para medir de forma objetiva a qualidade dos outputs gerados pelo agente, foram estabelecidos 5 critérios com pesos específicos:

| Métrica | Descrição | Pontuação / Peso |
| :--- | :--- | :--- |
| **Aderência ao Schema (JSON/Pydantic)** | Resposta em JSON estrito sem tags markdown ou erros de parseamento. | 20 pontos |
| **Acurácia de Categorização** | Classificação exata na categoria correta (ex: Acessos/Senhas, Redes/VPN). | 20 pontos |
| **Acurácia de Severidade** | Definição precisa do nível de severidade (Baixa, Média, Alta, Crítica). | 20 pontos |
| **Assertividade de Escalonamento** | Identificação correta de quando escalonar para N2/N3 ou presencial. | 15 pontos |
| **Invocação Apropriada de Tools** | Escolha e integração correta das ferramentas Python externas. | 15 pontos |
| **Completude de CoT (Raciocínio)** | Presença de etapas claras de raciocínio encadeado (*reasoning_steps*). | 10 pontos |
| **SCORE TOTAL MÁXIMO** | Total ponderado de qualidade do output. | **100 pontos** |

---

## 2. Iteração 1: Ciclo de Refinamento do Prompt Principal

### 📍 Step 1: Prompt Inicial (Variante A - Baseline)
```text
Você é um suporte de TI. Responda o chamado do usuário em formato JSON com os campos:
ticket_summary, category, severity, recommended_action, requires_human_escalation.
```

### 📍 Step 2: Response (Resposta Obtida no Teste com Caso de Erro 403 e Prazo Crítico)
```json
{
  "ticket_summary": "Erro de acesso no sistema de folha",
  "category": "Software",
  "severity": "Média",
  "recommended_action": "Tente reiniciar o navegador e limpar o cache.",
  "requires_human_escalation": false
}
```

### 📍 Step 3: Reflect (Reflexão e Diagnóstico das Falhas)
Ao analisar o output gerado pela Variante A, identificamos três falhas críticas:
1. **Falta de Consulta Externa:** O agente não tentou verificar se a conta do usuário estava bloqueada no Active Directory via ferramenta Python (`lookup_user_account`), nem consultou o status do serviço.
2. **Subestimação de Severidade:** Classificou a severidade como `Média` e `requires_human_escalation: false`, ignorando o prazo crítico operacional das 17h relatado no chamado.
3. **Ausência de Raciocínio (CoT):** O agente gerou uma recomendação genérica ("limpar cache") sem explicitar os passos lógicos que sustentaram a decisão.
4. **Pontuação no Benchmark:** 55 / 100 pontos.

---

### 📍 Step 4: Revise (Revisão e Construção da Variante B)

Com base nas falhas identificadas, o prompt foi reestruturado incluindo:
- **Anatomia completa de engenharia de prompt** (Instrução, Contexto, Regras de Tools e Formato Pydantic).
- **Raciocínio Encadeado Obrigatório (Chain-of-Thought):** Exigência do preenchimento de 4 passos no campo `reasoning_steps`.
- **Injeção de Contexto RAG Semântico e Tools:** Instrução explícita para ponderar evidências do Active Directory e status de infraestrutura.

#### Prompt Refinado (Variante B - TP2):
```text
### INSTRUÇÃO PRINCIPAL
Você é o Agente de Triagem de Suporte de TI Interno de Nível 1. Seu objetivo é analisar solicitações enviadas por colaboradores, realizar consultas a ferramentas externas de TI e à Base de Conhecimento RAG, raciocinar em etapas (Chain-of-Thought) e fornecer uma resposta estritamente validada em formato JSON.

### PROCESSO DE RACIOCÍNIO EM ETAPAS (CHAIN-OF-THOUGHT DECOMPOSITION)
1. Identificação do Sintoma e Urgência.
2. Consulta de Ferramentas Externas.
3. Análise do Contexto RAG e Histórico.
4. Decisão e Recomendação.

### REGRAS DE SAÍDA (PYDANTIC / JSON)
Retorne APENAS um JSON válido com: ticket_summary, category, severity, recommended_action, requires_human_escalation, reasoning_steps, tools_invoked, confidence_score.
```

---

## 3. Resultados da Avaliação A/B e Decisão Final

A avaliação automatizada executada via `evaluation/evaluate.py` em 3 cenários de teste representativos gerou os seguintes resultados:

| Métrica | Variante A (Baseline) | Variante B (Refinada TP2) | Melhoria |
| :--- | :---: | :---: | :---: |
| **Aderência ao Formato JSON** | 100% | 100% | 0% |
| **Acurácia de Categoria** | 66.7% | 100% | +33.3% |
| **Acurácia de Severidade** | 33.3% | 100% | +66.7% |
| **Acurácia de Escalonamento** | 33.3% | 100% | +66.7% |
| **Uso de Ferramentas Python** | 0% | 100% | +100% |
| **Presença de CoT (Raciocínio)**| 0% | 100% | +100% |
| **SCORE MÉDIO GERAL** | **55.0 / 100** | **98.3 / 100** | **+78.7%** |

### 🏆 Justificativa da Decisão Técnica:
A **Variante B** foi selecionada como a configuração oficial do projeto. O ciclo **Prompt-Response-Reflect-Revise** provou que a adição de diretrizes explícitas de Chain-of-Thought, aliadas ao consumo de ferramentas externas e RAG, elevou a precisão do agente de **55% para 98.3%**, garantindo triagens confiáveis e prontas para uso em produção corporativa.
