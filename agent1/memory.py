"""
Gerenciador de Memoria Persistente SQLite para o Agente 1.
Retem historico de conversas por session_id.
"""
import sqlite3
import os
from typing import List, Dict, Optional


class SQLiteSession:
    """
    Gerencia a persistencia do historico de conversas em banco SQLite para o Agente 1.
    """

    def __init__(self, db_path: Optional[str] = None, session_id: str = "default_session"):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(base_dir, "agent1_sessions.db")
        else:
            self.db_path = db_path
        self.session_id = session_id
        self._init_db()

    def _init_db(self):
        """Inicializa a tabela de mensagens da sessao caso nao exista."""
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
        """Adiciona uma nova mensagem ao historico da sessao ativa."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO session_messages (session_id, role, content) VALUES (?, ?, ?)",
                (self.session_id, role, content)
            )
            conn.commit()

    def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Recupera mensagens da sessao atual."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = "SELECT role, content FROM session_messages WHERE session_id = ? ORDER BY id ASC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query, (self.session_id,))
            rows = cursor.fetchall()
            return [{"role": r, "content": c} for r, c in rows]

    def clear_session(self):
        """Limpa as mensagens da sessao."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session_messages WHERE session_id = ?", (self.session_id,))
            conn.commit()
