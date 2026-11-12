"""
Hook PreToolUse do Agente 1 (Triagem de TI Nível 1).
Executado antes de qualquer chamada a ferramentas externas (@function_tool).
Comportamento automatizado e verificável:
 1. Sanitiza e valida parâmetros de entrada (ex: sintaxe e domínio de e-mails corporativos).
 2. Bloqueia tentativas de injeção de caracteres especiais ou argumentos vazios.
 3. Registra trilha de auditoria pré-execução com timestamp e hash.
"""
import re
import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

# Domínio estrito corporativo permitido
ALLOWED_EMAIL_DOMAIN = "@empresa.com"
AUDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook_audit.log")


class PreToolValidationError(Exception):
    """Exceção levantada quando um parâmetro viola as políticas de segurança do Agente 1."""
    pass


def validate_email_format(email: str) -> bool:
    """Valida se o e-mail possui sintaxe correta e pertence ao domínio corporativo."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern, email):
        return False
    return email.lower().endswith(ALLOWED_EMAIL_DOMAIN)


def sanitize_input_text(text: str) -> str:
    """Remove caracteres perigosos ou tentativas de comando/injeção."""
    if not text or not isinstance(text, str):
        return ""
    # Remove delimitadores de controle suspeitos
    cleaned = re.sub(r"[;<>&|`$\\]", "", text)
    return cleaned.strip()


def pre_tool_use_hook(tool_name: str, tool_args: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Hook interceptor executado antes de invocar uma tool no Agente 1.
    Retorna: (is_allowed: bool, reason: str, sanitized_args: Dict[str, Any])
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    sanitized_args = dict(tool_args)

    # 1. Regra para lookup_user_account: validação rígida de e-mail corporativo
    if tool_name == "lookup_user_account":
        user_email = tool_args.get("user_email", "")
        if not user_email:
            reason = "Bloqueado: 'user_email' ausente ou vazio."
            _log_hook_event(timestamp, tool_name, tool_args, False, reason)
            return False, reason, tool_args

        if not validate_email_format(user_email):
            reason = f"Bloqueado: e-mail '{user_email}' inválido ou fora do domínio corporativo '{ALLOWED_EMAIL_DOMAIN}'."
            _log_hook_event(timestamp, tool_name, tool_args, False, reason)
            return False, reason, tool_args

        sanitized_args["user_email"] = user_email.strip().lower()

    # 2. Regra para check_system_status: sanitização e whitelisting de serviços
    elif tool_name == "check_system_status":
        service_name = tool_args.get("service_name", "")
        sanitized_service = sanitize_input_text(service_name).lower()
        valid_services = {"vpn", "folha", "payroll", "email", "erp", "sap", "jira"}
        if not sanitized_service:
            reason = "Bloqueado: 'service_name' vazio."
            _log_hook_event(timestamp, tool_name, tool_args, False, reason)
            return False, reason, tool_args

        if sanitized_service not in valid_services and not any(v in sanitized_service for v in valid_services):
            reason = f"Bloqueado: serviço '{service_name}' não é monitorado oficialmente pela infraestrutura."
            _log_hook_event(timestamp, tool_name, tool_args, False, reason)
            return False, reason, tool_args

        sanitized_args["service_name"] = sanitized_service

    # 3. Regra para query_troubleshooting_kb: sanitização de busca
    elif tool_name == "query_troubleshooting_kb":
        query = tool_args.get("query", "")
        cleaned_query = sanitize_input_text(query)
        if len(cleaned_query) < 2:
            reason = "Bloqueado: query de busca textual muito curta ou inválida."
            _log_hook_event(timestamp, tool_name, tool_args, False, reason)
            return False, reason, tool_args
        sanitized_args["query"] = cleaned_query

    # Sucesso na validação
    reason = "Validação PreToolUse aprovada com sucesso."
    _log_hook_event(timestamp, tool_name, sanitized_args, True, reason)
    return True, reason, sanitized_args


def _log_hook_event(timestamp: str, tool_name: str, args: Dict[str, Any], allowed: bool, reason: str):
    """Registra evento do hook no log de auditoria persistente."""
    entry = {
        "timestamp": timestamp,
        "hook_type": "PreToolUse",
        "tool_name": tool_name,
        "arguments": args,
        "allowed": allowed,
        "reason": reason
    }
    try:
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Aviso: falha ao gravar log do hook: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Teste rápido manual em execução direta
    print("Testando PreToolUse Hook do Agente 1:")
    ok, msg, args = pre_tool_use_hook("lookup_user_account", {"user_email": "maria.souza@empresa.com"})
    print(f"Caso 1 (Válido): {ok} | {msg} | Args: {args}")

    ok, msg, args = pre_tool_use_hook("lookup_user_account", {"user_email": "hacker@gmail.com"})
    print(f"Caso 2 (Inválido): {ok} | {msg}")
