---
name: sla-incident-dispatch
description: Protocolo operacional e matriz de decisão para cálculo de SLA e despacho formal de incidentes técnicos no sistema ITSM corporativo.
version: 1.0.0
author: João Pedro Barboza
tags:
  - itsm
  - sla-calculation
  - incident-management
  - escalation-policy
parameters:
  ticket_id:
    type: string
    description: Código identificador do chamado original triado (ex: TCK-40301-BR).
    required: true
  severity:
    type: string
    description: Nível de severidade triado pelo Agente 1 (Critica, Alta, Media, Baixa).
    required: true
  team:
    type: string
    description: Equipe técnica responsável pelo atendimento (N2 Infraestrutura, N2 Acessos, Suporte Presencial N2).
    required: true
  justification:
    type: string
    description: Razão técnica detalhada do escalonamento.
    required: true
---

# Skill: Governança de SLA e Despacho de Incidentes ITSM

Esta skill define as regras de governança para o **Agente 2 (Auto-Remediação e Despacho N2)** calcular rigorosamente as metas de tempo de atendimento (SLA) e lavrar o despacho de incidentes.

---

## ⏱️ Matriz Corporativa de SLA por Severidade

A meta de resposta e contenção técnica obedece à tabela mandatória da organização:

| Severidade | Meta de SLA (Minutos) | Tempo Equivalente | Cenários Típicos |
| :--- | :---: | :---: | :--- |
| **Crítica** | **30 min** | 0.5 hora | Falha global em gateway de VPN, ERP fora do ar em fechamento contábil. |
| **Alta** | **120 min** | 2.0 horas | Conta de gestor bloqueada em dia de folha de pagamento, falha de rede departamental. |
| **Média** | **480 min** | 8.0 horas (1 dia útil) | Lentidão intermitente em aplicação secundária, solicitação de permissão de software. |
| **Baixa** | **1440 min** | 24.0 horas (3 dias úteis)| Dúvida de configuração, solicitação de periféricos ou agendamento de manutenção. |

---

## 📋 Protocolo de Execução Passo a Passo

### Passo 1: Validação do Chamado
- Verificar integridade do `ticket_id` e conferir se o chamado já foi registrado anteriormente para evitar duplicidade no ITSM.

### Passo 2: Computação do SLA
- Normalizar o campo `severity` para minúsculo.
- Consultar a tabela de SLA e definir o valor inteiro `sla_target_minutes`.

### Passo 3: Identificação do Plantonista e Roteamento de Equipe
- **N2 Infraestrutura:** Responsável por gateways de VPN, switches, roteamento e conectividade de rede.
- **N2 Acessos e Identidade:** Responsável por Active Directory, Azure AD/Entra ID, federação e MFA.
- **Suporte Presencial N1/N2:** Responsável por problemas físicos de hardware, cabeamento, troca de monitores e fontes.

### Passo 4: Geração do Registro ITSM
- Acionar a ferramenta `dispatch_sla_incident`:
  - Gerar código `INC-YYYYMM-XXXXXX`.
  - Associar o engenheiro de plantão (`on_call_engineer`).
  - Carimbar timestamp UTC imutável.

### Passo 5: Geração de Hash de Conformidade
- O hook PostToolUse intercepta a criação e injeta o `compliance_hash: SEC-XXXX`, garantindo rastreabilidade perante auditorias SOX e ISO 27001.
