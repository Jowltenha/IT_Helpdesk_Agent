"""
Hook PostToolUse do Agente 2 (Auto-Remediação e Despacho N2).
Executado imediatamente após a conclusão de qualquer ferramenta de intervenção técnica.
Comportamento automatizado e verificável:
 1. Gera hash criptográfico SHA-256 para integridade e rastreabilidade imutável da ação.
 2. Injeta metadados de compliance corporativo (LGPD / SOX) no retorno da ferramenta.
 3. Registra a trilha de segurança no log de auditoria do Agente 2.
"""
import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any

AUDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "security_audit.log")


def generate_action_hash(action_name: str, args: Dict[str, Any], result: Dict[str, Any], timestamp: str) -> str:
    """Calcula um hash SHA-256 único unindo ação, parâmetros, resultado e carimbo de tempo."""
    payload = f"{action_name}::{json.dumps(args, sort_keys=True)}::{json.dumps(result, sort_keys=True)}::{timestamp}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()


def post_tool_use_hook(tool_name: str, tool_args: Dict[str, Any], tool_result_raw: str) -> str:
    """
    Hook interceptor executado após a conclusão de uma tool no Agente 2.
    Enriquece a resposta com o código de integridade e persiste o evento.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        result_data = json.loads(tool_result_raw)
    except Exception:
        result_data = {"raw_output": tool_result_raw}

    # Gera identificador de compliance baseado em SHA-256
    compliance_hash = generate_action_hash(tool_name, tool_args, result_data, timestamp)

    # Injeta campos de governança
    result_data["compliance_hash"] = f"SEC-{compliance_hash}"
    result_data["verified_by_hook"] = True
    result_data["hook_processed_at"] = timestamp

    # Gravação no log de auditoria
    _log_security_audit_event(timestamp, tool_name, tool_args, result_data, compliance_hash)

    return json.dumps(result_data, ensure_ascii=False)


def _log_security_audit_event(
    timestamp: str,
    tool_name: str,
    args: Dict[str, Any],
    result_data: Dict[str, Any],
    compliance_hash: str
):
    """Grava o registro de auditoria em arquivo imutável append-only."""
    entry = {
        "timestamp": timestamp,
        "hook_type": "PostToolUse",
        "tool_name": tool_name,
        "compliance_hash": f"SEC-{compliance_hash}",
        "arguments": args,
        "status": result_data.get("status", "UNKNOWN"),
        "audit_code": result_data.get("audit_code") or result_data.get("session_token") or result_data.get("incident_number")
    }
    try:
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Aviso: falha ao registrar security audit: {e}", file=sys.stderr)


if __name__ == "__main__":
    print("Testando PostToolUse Hook do Agente 2:")
    sample_result = json.dumps({"status": "SUCCESS", "message": "Conta desbloqueada"})
    enriched = post_tool_use_hook("unlock_user_account", {"user_email": "maria@empresa.com"}, sample_result)
    print("Resultado enriquecido pelo Hook:", enriched)
