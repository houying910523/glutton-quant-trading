from __future__ import annotations

from pathlib import Path

from modules.config import DEFAULT_DB_PATH, DEFAULT_RAW_ROOT, PROJECT_ROOT
from modules.repositories.database import SQLiteDatabase
from modules.repositories.schema import SQLiteSchemaManager
from modules.datasource.pipeline.raw_store import RawStore


class JobRuntime:
    def __init__(self):
        self._database = SQLiteDatabase(_resolve_project_path(DEFAULT_DB_PATH))
        self._raw_store = RawStore(_resolve_project_path(DEFAULT_RAW_ROOT))
        self._schema_manager = SQLiteSchemaManager(self._database)
        self._schema_manager.initialize()

    @property
    def database(self) -> SQLiteDatabase:
        return self._database

    @property
    def raw_store(self) -> RawStore:
        return self._raw_store


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
