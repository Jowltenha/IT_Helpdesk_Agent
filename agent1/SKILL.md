---
name: active-directory-diagnostics
description: Procedimento operacional padrão (SOP) para diagnóstico aprofundado de bloqueios de conta corporativa, erros de permissão 403 e validação de privilégios no Active Directory.
version: 1.0.0
author: João Pedro Barboza
tags:
  - active-directory
  - triage-n1
  - identity
  - access-control
parameters:
  user_email:
    type: string
    description: E-mail corporativo institucional do colaborador sob análise (deve terminar em @empresa.com).
    required: true
  system_context:
    type: string
    description: Nome da aplicação corporativa impactada (ex: Folha de Pagamento, ERP SAP, E-mail).
    required: false
---

# Skill: Diagnóstico Aprofundado de Identidade e Active Directory

Esta skill encapsula a capacidade procedural de investigar e diagnosticar falhas de autenticação, permissão 403 e bloqueios de credenciais no ambiente corporativo para o **Agente 1 (Triagem N1)**.

---

## 🎯 Objetivo Operacional

Orientar a análise de contas de usuário no Active Directory (AD) para determinar com precisão se a falha relatada decorre de:
1. **Conta Bloqueada (`account_locked = True`):** Excedeu o número máximo de tentativas incorretas de senha.
2. **Ausência de Grupo de Acesso:** Falta de permissão no perfil (ex: falta de `Folha_Pagamento_Admin` ou `VPN_Users`).
3. **Instabilidade Sistêmica do Serviço:** Quando o sistema de destino (ERP, Folha) está fora do ar ou em manutenção, e a conta do usuário está íntegra.

---

## 📋 Protocolo de Execução Passo a Passo

### Passo 1: Sanitização Prévia do E-mail
- Verificar se o e-mail informado possui formato padrão corporativo (`@empresa.com`).
- Bloquear tentativas de injeção ou caracteres fora do padrão RFC 5322.

### Passo 2: Consulta à Ferramenta `lookup_user_account`
- Invocar a ferramenta passando o e-mail sanitizado.
- Avaliar a resposta JSON:
  - Se `account_locked: true`: Identificar o estado como incidente crítico de acesso.
  - Se `account_locked: false`: Inspecionar a lista `groups` para verificar se o usuário pertence ao grupo do sistema solicitado.
  - Se `status: "Nao Encontrado"`: Classificar como cadastro inexistente e direcionar para RH/Onboarding.

### Passo 3: Correlação com `check_system_status`
- Se o usuário reportou erro no sistema "Folha de Pagamento", consultar `check_system_status("folha")`.
- Se o serviço estiver em "Manutencao" ou "Degradado", o problema é de infraestrutura global, **não** da conta individual.

### Passo 4: Cruzamento com Artigos procedurais da Base de Conhecimento (RAG)
- Recuperar artigo `KB-101` para resolução de 403 ou `KB-104` para políticas de senha.
- Extrair o procedimento exato (ex: necessidade de MFA, limpeza de cache ou intervenção N2).

### Passo 5: Formulação do Parecer Estruturado
- Preencher o schema Pydantic `HelpdeskResponse`:
  - `category`: `"Acessos/Senhas"`
  - `severity`: `"Alta"` (se bloqueada em horário crítico) ou `"Critica"` (se diretoria/folha de fechamento).
  - `requires_human_escalation`: `false` se houver remediação automatizada via Agente 2, ou `true` se exigir intervenção humana formal.
  - `recommended_action`: Instrução acionável para o Agente 2 ou equipe de suporte.

---

## 💡 Exemplos de Entrada e Saída

### Exemplo 1: Bloqueio no Active Directory
- **Entrada:** `user_email = "maria.souza@empresa.com"`, `system_context = "Folha de Pagamento"`
- **Diagnóstico:** Conta bloqueada por 5 tentativas inválidas. Sistema de folha operacional. Grupo `Folha_Pagamento_Admin` presente.
- **Ação:** Solicitar desbloqueio automático no Active Directory via Agente 2 e reset de falhas.

### Exemplo 2: Ausência de Permissão
- **Entrada:** `user_email = "joao.silva@empresa.com"`, `system_context = "Folha de Pagamento"`
- **Diagnóstico:** Conta ativa (`account_locked: false`), porém possui apenas grupo `Folha_Pagamento_Leitura` e tentou executar alteração administrativa (Erro 403 legítimo).
- **Ação:** Escalonamento humano para aprovação de perfil com a gerência do solicitante.
