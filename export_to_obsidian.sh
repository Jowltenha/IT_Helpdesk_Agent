#!/bin/bash
VAULT_DIR="/mnt/c/Users/joaop/OneDrive/Área de Trabalho/AT_PB"

if [ ! -d "$VAULT_DIR" ]; then
  echo "❌ Diretório do Vault não encontrado: $VAULT_DIR"
  exit 1
fi

echo "📋 Copiando arquivos para o Obsidian Vault..."
cp -v /home/jowlt/IT_Helpdesk_Agent/RESUMO_COMPONENTES_OBSIDIAN.md "$VAULT_DIR/"
cp -v /home/jowlt/IT_Helpdesk_Agent/OBSIDIAN_RELATORIO_ARQUITETURA.md "$VAULT_DIR/"
cp -v /home/jowlt/IT_Helpdesk_Agent/RELATORIO_TECNICO_TP4_OBSIDIAN.md "$VAULT_DIR/"
cp -v /home/jowlt/IT_Helpdesk_Agent/diagrama_arquitetura_9_componentes.svg "$VAULT_DIR/"

echo "✅ Sucesso! Os arquivos foram exportados para o seu Obsidian."
