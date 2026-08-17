# Documentação dos Prompts e Anatomia do Sistema

## 1. Anatomia do Prompt (`SYSTEM_INSTRUCTION`)

O prompt utilizado no agente foi estruturado nas quatro seções fundamentais de engenharia de prompt:

### A. Instrução (Instruções Principais)
> "Você é o Agente de Triagem de Suporte de TI Interno. Seu objetivo é analisar solicitações enviadas por colaboradores, classificar a natureza do problema e fornecer orientações iniciais."

### B. Contexto
> "Você opera no nível 1 do suporte técnico de uma empresa. Seu papel é agilizar a triagem antes que os chamados sejam atribuídos aos analistas."

### C. Exemplos (Few-Shot Prompting)
> - **Entrada:** *"Minha tela ficou preta e o computador não liga mais."*  
>   **Saída Esperada:** `category="Hardware"`, `severity="Alta"`, `requires_human_escalation=true`.
> - **Entrada:** *"Esqueci minha senha do e-mail corporativo."*  
>   **Saída Esperada:** `category="Acessos/Senhas"`, `severity="Baixa"`, `requires_human_escalation=false`.

### D. Formato de Saída e Restrições
> "Você DEVE retornar APENAS um objeto JSON válido cujas chaves coincidam EXATAMENTE com o schema especificado abaixo. NÃO traduza nem modifique o nome dos campos."
> - `ticket_summary` (string): Resumo do problema em até 10 palavras.
> - `category` (string): Categoria ("Hardware", "Software", "Redes/VPN", "Acessos/Senhas", "Outros").
> - `severity` (string): Severidade ("Baixa", "Média", "Alta", "Crítica").
> - `recommended_action` (string): Passos recomendados.
> - `requires_human_escalation` (boolean): true ou false.

---

## 2. Registro de Execução e Output de Teste

### Entrada Utilizada no Teste:
> *"Não consigo acessar o sistema de folha de pagamento e preciso enviar o relatório até 17h. Aparece o erro 'Acesso Negado 403'."*

### Saída Estruturada Gerada pelo Agente (`execution_log.json`):
```json
{
  "ticket_summary": "Erro 403 ao acessar sistema de folha de pagamento",
  "category": "Acessos/Senhas",
  "severity": "Alta",
  "recommended_action": "1. Verificar se o usuário possui perfil de acesso ativo no sistema de folha de pagamento. 2. Confirmar se houve alteração recente de senha ou permissões. 3. Solicitar ao administrador do sistema a revisão e reativação das permissões de acesso do usuário. 4. Caso não resolvido em 30 minutos, escalar para N2 dado o prazo crítico de 17h.",
  "requires_human_escalation": true
}

---

### 3. Reorganização dos Arquivos do Repositório

No seu terminal Linux/WSL, execute os comandos abaixo para organizar as pastas exatamente como pedido:

```bash
# 1. Certifique-se de estar na raiz do seu projeto
cd ~/IT_Helpdesk_Agent

# 2. Crie os diretórios obrigatórios
mkdir -p agent spec prompts

# 3. Mova os arquivos existentes da raiz para a pasta agent/
mv main.py agent/
mv execution_log.json agent/
mv requirements.txt agent/
mv .env.example agent/

# 4. Mova a pasta src/ para dentro de agent/ (se houver arquivos nela)
mv src agent/