# Especificação do Projeto e Arquitetura Inicial

## 1. Descrição do Problema
No ambiente corporativo, a equipe de suporte de TI (Nível 1 / Helpdesk) lida diariamente com um elevado volume de solicitações informais e não estruturadas enviadas por colaboradores via e-mail ou chat. A triagem manual desses chamados gera atrasos na identificação de urgências, inconsistência na categorização e alocação ineficiente de analistas especializados.

O objetivo deste projeto é automatizar a fase de triagem do suporte Nível 1 por meio de um Agente de IA. O agente analisa o texto livre enviado pelo colaborador, determina a natureza do problema, define o nível de severidade, sugere ações imediatas de autoatendimento e identifica se há necessidade de escalonamento presencial ou para equipes N2/N3.

## 2. Arquitetura da Solução

### Diagrama de Fluxo de Dados
`[Entrada do Usuário (Texto Livre)]` ➡️ `[Agente de Triagem (LLM + Prompt Anatomizado)]` ➡️ `[Validador de Schema (Pydantic)]` ➡️ `[Terminal / execution_log.json]`

### Componentes do Sistema
1. **Entrada de Dados (`User Prompt`):** Texto em linguagem natural descrevendo a falha técnica ou dúvida do colaborador.
2. **Motor de Inferência / Agente de IA:** Utilização do cliente `AsyncOpenAI` conectado ao proxy de modelos local (**9Router Proxy / Antigravity**) executando o modelo `ag/claude-sonnet-4-6`.
3. **Engenharia de Prompt:** Instruções estruturadas seguindo a anatomia recomendada (Instrução, Contexto, Exemplos, Formato de Saída e Restrições).
4. **Camada de Validação e Formatação (`Pydantic`):** Modelo de dados `HelpdeskResponse` que garante a integridade dos campos e tipos de dados retornados pela LLM.
5. **Persistência de Logs (`execution_log.json`):** Registro em arquivo JSON local com o resultado validado da execução para auditoria e integração com outros sistemas.

## 3. Justificativas Técnicas

- **Python & Pydantic v2:** A escolha do Pydantic garante *type safety* e parseamento determinístico de dados não estruturados gerados pela LLM, evitando erros de contrato ao integrar a IA com APIs ou bancos de dados downstream.
- **Cliente AsyncOpenAI (`asyncio`):** Permite chamadas assíncronas de I/O, otimizando o tempo de resposta da aplicação para execuções simultâneas ou escaláveis.
- **Roteamento via 9Router Proxy:** Garante flexibilidade de provedores e privacidade/controle de infraestrutura ao intermediar requisições para modelos como Claude e Gemini de forma transparente e compatível com a API da OpenAI.