from __future__ import annotations

import sqlite3


class SQLiteRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
