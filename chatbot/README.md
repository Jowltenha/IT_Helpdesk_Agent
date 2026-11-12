# 💬 Chatbot Corporativo de Autoatendimento de TI (Chainlit)

Este módulo implementa o **Componente 9 do Sistema (Slide 8)**:
> **"Gatilho (trigger) que dispara o workflow n8n — Escolha única: Chatbot Corporativo Web via Webhook"**

---

## 🎯 Função no Sistema

1. **Interface Conversacional do Colaborador:** Ponto de entrada amigável onde colaboradores corporativos descrevem seus problemas técnicos em texto livre.
2. **Manutenção do `session_id`:** O Chainlit gerencia a sessão conversacional do usuário, repassando o identificador para a `SQLiteSession` do Agente 1 (mantendo o histórico conversacional ativo).
3. **Disparo do Webhook do n8n:** Ao receber a mensagem, encaminha a requisição HTTP POST para o endpoint do webhook do n8n (`http://localhost:5678/webhook/helpdesk-triage`).
4. **Fallback Transparente:** Caso o n8n não esteja rodando em modo teste, o Chatbot consulta diretamente a API assíncrona do Agente 1 (`POST /run` e polling em `GET /status/{task_id}`).
5. **Renderização Rica:** Exibe resumo do ticket, categoria, severidade, recomendação, etapas de raciocínio CoT e ferramentas acionadas.

---

## 🚀 Como Executar

### 1. Ativar o Ambiente Virtual e Instalar o Chainlit
```bash
source .venv/bin/activate
pip install chainlit
```

### 2. Iniciar o Chatbot
```bash
chainlit run chatbot/app.py -w
```
O Chainlit abrirá automaticamente no navegador em `http://localhost:8000`.

### 3. Exemplo de Teste no Chatbot
Envie a mensagem:
> *"Não consigo acessar a folha de pagamento. Erro 403 Acesso Negado. E-mail maria.souza@empresa.com. Urgente até 17h."*

O Chatbot disparará a esteira, aguardará o processamento da LLM e exibirá o diagnóstico completo formatado em tabela com as etapas CoT e a ferramenta `lookup_user_account` executada.
