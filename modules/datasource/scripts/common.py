from __future__ import annotations

from modules.repositories.database import SQLiteDatabase
from modules.repositories.schema import SQLiteSchemaManager
from modules.datasource.pipeline.raw_store import RawStore


class JobRuntime:
    def __init__(self):
        self._database = SQLiteDatabase()
        self._raw_store = RawStore()
        self._schema_manager = SQLiteSchemaManager(self._database)
        self._schema_manager.initialize()

    @property
    def database(self) -> SQLiteDatabase:
        return self._database

    @property
    def raw_store(self) -> RawStore:
        return self._raw_store
