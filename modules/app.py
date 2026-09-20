from modules.repositories.database import SQLiteDatabase
from modules.repositories.schema import SQLiteSchemaManager


class App:
    def __init__(self):
        self._database = SQLiteDatabase()
        self._schema_manager = SQLiteSchemaManager(self._database)
        self._schema_manager.initialize()

    @property
    def database(self) -> SQLiteDatabase:
        return self._database


if __name__ == "__main__":
    app = App()
    app.start()
