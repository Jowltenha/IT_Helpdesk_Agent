"""
Gerenciador de Memória Persistente usando a SQLiteSession do OpenAI Agents SDK.
Atende ao Requisito 2 do projeto: Memória conversacional persistente para o Agente 1.
"""
import os
from pathlib import Path
from typing import Optional, Union

try:
    from agents.memory import SQLiteSession as SDKSQLiteSession
    HAS_AGENTS_SDK = True
except ImportError:
    HAS_AGENTS_SDK = False


DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent1_sessions.db")


class SQLiteSession:
    """
    Wrapper e fábrica para a SQLiteSession oficial do OpenAI Agents SDK.
    Garante que o Agente 1 mantenha histórico persistente de conversas entre turnos.
    """

    def __init__(self, session_id: str = "default_session", db_path: Optional[Union[str, Path]] = None):
        self.session_id = session_id
        self.db_path = str(db_path) if db_path else DEFAULT_DB_PATH

        if HAS_AGENTS_SDK:
            self._sdk_session = SDKSQLiteSession(
                session_id=self.session_id,
                db_path=self.db_path
            )
        else:
            self._sdk_session = None

    @property
    def sdk_session(self):
        """Retorna a instância real do SDK SQLiteSession para ser passada ao Runner.run."""
        return self._sdk_session

    def get_session_id(self) -> str:
        return self.session_id

    def get_db_path(self) -> str:
        return self.db_path


__all__ = ["SQLiteSession", "DEFAULT_DB_PATH"]
