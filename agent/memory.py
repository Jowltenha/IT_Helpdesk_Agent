"""
Gerenciador de Memória Persistente usando SQLiteSession.
Permite salvar e recuperar o histórico de conversação entre execuções distintas do agente.
"""
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional


class SQLiteSession:
    """
    Gerencia a persistência do histórico de conversas em banco de dados SQLite.
    Permite ao agente manter o contexto de interações anteriores entre chamadas.
    """

    def __init__(self, db_path: str = "agent_sessions.db", session_id: str = "default_session"):
        self.db_path = db_path
        self.session_id = session_id
        self._init_db()

    def _init_db(self):
        """Inicializa a tabela de sessões no banco SQLite caso não exista."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def add_message(self, role: str, content: str):
        """Adiciona uma nova mensagem ao histórico da sessão ativa."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO session_messages (session_id, role, content) VALUES (?, ?, ?)",
                (self.session_id, role, content)
            )
            conn.commit()

    def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Recupera as mensagens salvas da sessão no formato de dicionários para a LLM."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = "SELECT role, content FROM session_messages WHERE session_id = ? ORDER BY id ASC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query, (self.session_id,))
            rows = cursor.fetchall()
            return [{"role": r, "content": c} for r, c in rows]

    def clear_session(self):
        """Limpa todo o histórico de mensagens da sessão atual."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session_messages WHERE session_id = ?", (self.session_id,))
            conn.commit()

    def list_sessions(self) -> List[str]:
        """Retorna todas as IDs de sessão registradas no banco."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT session_id FROM session_messages")
            return [row[0] for row in cursor.fetchall()]
