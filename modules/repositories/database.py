from __future__ import annotations

import sqlite3
from pathlib import Path

from modules.config import resolve_project_path, DEFAULT_DB_PATH


class SQLiteDatabase:
    default_db_path = resolve_project_path(DEFAULT_DB_PATH)

    def __init__(self, db_path: str | Path = default_db_path) -> None:
        self._db_path = Path(db_path)

    @property
    def path(self) -> Path:
        return self._db_path

    def connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection
