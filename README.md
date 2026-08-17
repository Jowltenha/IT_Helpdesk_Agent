# Agente de Triagem de TI - Helpdesk Interno (TP1)

Este projeto implementa um agente de inteligência artificial responsável pela triagem automática de chamados de suporte técnico de nível 1. O agente analisa a mensagem enviada pelo colaborador, classifica a natureza e a severidade do problema, recomenda ações imediatas e retorna uma resposta estritamente estruturada em JSON utilizando **Pydantic**.

---

## 🚀 Tecnologias Utilizadas

- **Python 3.14**
- **Pydantic v2** (Validação de schemas e saída estruturada)
- **OpenAI Python SDK (`AsyncOpenAI`)**
- **python-dotenv** (Gerenciamento de variáveis de ambiente)
- **9Router Proxy / Antigravity** (Roteamento e compatibilidade de modelos)

---

## 📋 Pré-requisitos

- Python 3.10 ou superior instalado.
- Proxy de LLM ativo e configurado (ex.: 9Router Proxy com o provedor Antigravity).

---

## ⚙️ Configuração do Ambiente

1. **Clone o repositório:**
   ```bash
   git clone <URL_DO_SEU_REPOSITORIO>
   cd IT_Helpdesk_Agent

```

2. **Crie e ative o ambiente virtual:**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

```


3. **Instale as dependências:**
```bash
pip install -r requirements.txt

```


4. **Configure as variáveis de ambiente:**
* Duplique o arquivo `.env.example` e renomeie para `.env`:
```bash
cp .env.example .env

```


* Preencha os campos no arquivo `.env` com as suas credenciais do proxy local:
```env
OPENAI_API_KEY=sk-2a...
OPENAI_BASE_URL=http://localhost:20128/v1

```





---

## 🏃 Como Executar

Com o ambiente virtual ativo e o proxy local operando, execute o script principal:

```bash
python main.py

```

---

## 📄 Estrutura da Saída

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
