"""
Script de teste automatizado para o Hook PreToolUse do Agente 1.
Verifica o comportamento esperado com casos de aprovação e bloqueio.
"""
import os
import json
from agent1.hooks.pre_tool_validator import pre_tool_use_hook, AUDIT_LOG_PATH


def run_tests():
    print("=== EXECUTANDO TESTES DO HOOK PRETOOLUSE (AGENTE 1) ===")

    # Limpa log anterior para o teste se existir
    if os.path.exists(AUDIT_LOG_PATH):
        try:
            os.remove(AUDIT_LOG_PATH)
        except Exception:
            pass

    test_cases = [
        {
            "name": "Consulta AD com e-mail corporativo válido",
            "tool": "lookup_user_account",
            "args": {"user_email": "joao.barboza@empresa.com"},
            "expected_allowed": True
        },
        {
            "name": "Bloqueio de e-mail externo (gmail.com)",
            "tool": "lookup_user_account",
            "args": {"user_email": "invasor@gmail.com"},
            "expected_allowed": False
        },
        {
            "name": "Bloqueio de tentativa de injeção em e-mail",
            "tool": "lookup_user_account",
            "args": {"user_email": "maria@empresa.com; rm -rf /"},
            "expected_allowed": False
        },
        {
            "name": "Consulta de serviço monitorado válido",
            "tool": "check_system_status",
            "args": {"service_name": "vpn"},
            "expected_allowed": True
        },
        {
            "name": "Bloqueio de serviço desconhecido ou malicioso",
            "tool": "check_system_status",
            "args": {"service_name": "servidor_secreto_xpto"},
            "expected_allowed": False
        },
        {
            "name": "Consulta RAG KB válida",
            "tool": "query_troubleshooting_kb",
            "args": {"query": "erro 403 folha"},
            "expected_allowed": True
        },
        {
            "name": "Bloqueio de query KB vazia",
            "tool": "query_troubleshooting_kb",
            "args": {"query": " "},
            "expected_allowed": False
        }
    ]

    all_passed = True
    for idx, tc in enumerate(test_cases, 1):
        allowed, reason, sanitized = pre_tool_use_hook(tc["tool"], tc["args"])
        passed = (allowed == tc["expected_allowed"])
        status_icon = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"[{idx}] {tc['name']}: {status_icon}")
        print(f"     Resultado: allowed={allowed} | Motivo: {reason}")
        if not passed:
            all_passed = False

    # Validação do arquivo de log
    assert os.path.exists(AUDIT_LOG_PATH), "Arquivo de auditoria do hook não foi gerado!"
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        log_lines = f.readlines()
    print(f"\nTotal de eventos registrados em hook_audit.log: {len(log_lines)}")
    assert len(log_lines) == len(test_cases), f"Esperado {len(test_cases)} registros no log, obtido {len(log_lines)}"

    if all_passed:
        print("\n🎉 TODOS OS TESTES DO HOOK PRETOOLUSE FORAM APROVADOS!")
    else:
        print("\n⚠️ ALGUNS TESTES FALHARAM!")
        exit(1)


if __name__ == "__main__":
    run_tests()
