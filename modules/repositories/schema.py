from __future__ import annotations


from modules.config import PROJECT_ROOT
from modules.repositories.database import SQLiteDatabase


class SQLiteSchemaManager:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database
        self._sql_dir = PROJECT_ROOT / "sql"

    def initialize(self) -> None:
        scripts = sorted(self._sql_dir.glob("*.sql"))
        with self._database.connect() as connection:
            for script_path in scripts:
                connection.executescript(script_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    schema_manager = SQLiteSchemaManager(SQLiteDatabase())
    schema_manager.initialize()
