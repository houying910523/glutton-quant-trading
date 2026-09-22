from pydantic import BaseModel

from modules.controller.base import rest_controller, get_mapping
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.utils.time_util import format_date


@rest_controller("/stock")
class StockController:
    def __init__(self):
        super().__init__()
        self.database = SQLiteDatabase()

    @get_mapping("/symbols")
    def list_symbols(
        self, symbol: str = "", name: str = "", page_no: int = 1, page_size: int = 40
    ):
        with RepositorySession(self.database) as session:
            return session.stock_info.list_symbols(symbol, name, page_no, page_size)

    @get_mapping("/daily")
    def get_stock_daily(self, stock_id: int, start_date: str, end_date: str):
        with RepositorySession(self.database) as session:
            rows = session.stock_daily.list_stock_daily(stock_id, start_date, end_date)
        return [
            StockDailyRow(
                stock_id=row.stock_id,
                trade_date=format_date(row.trade_date),
                open=row.open / 100,
                high=row.high / 100,
                low=row.low / 100,
                close=row.close / 100,
                volume=row.volume,
                amount=row.amount,
                turnover=row.turnover / 10000,
            )
            for row in rows
        ]


class StockDailyRow(BaseModel):
    stock_id: int
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: int
    turnover: float
