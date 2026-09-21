from modules.controller.base import rest_controller, get_mapping
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase


@rest_controller("/stock-info")
class StockInfoController:
    def __init__(self):
        super().__init__()
        self.database = SQLiteDatabase()

    @get_mapping("/symbols")
    def list_symbols(
        self, symbol: str = "", name: str = "", page_no: int = 1, page_size: int = 40
    ):
        with RepositorySession(self.database) as session:
            return session.stock_info.list_symbols(symbol, name, page_no, page_size)
