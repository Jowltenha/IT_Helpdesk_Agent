"""
Gerenciador de Memória Persistente usando a SQLiteSession do OpenAI Agents SDK.
Requisito 2 do projeto: Memória conversacional persistente para o Agente 1.
"""
import os
from pathlib import Path
from typing import Optional, Union

try:
    from agents.memory import SQLiteSession as SDKSQLiteSession
    HAS_AGENTS_SDK = True
except ImportError:
    HAS_AGENTS_SDK = False

DEFAULT_DB_PATH = "agent_sessions.db"


class SQLiteSession:
    """
    Wrapper para a SQLiteSession oficial do OpenAI Agents SDK.
    Permite ao agente manter o contexto de interações anteriores entre chamadas.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None, session_id: str = "default_session"):
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
        return self._sdk_session


__all__ = ["SQLiteSession", "DEFAULT_DB_PATH"]
