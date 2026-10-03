from typing import Optional


from modules.controller.base import rest_controller, get_mapping, post_mapping
from modules.controller.object import StockOptionalRequest, StockDailyRow
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.utils.time_util import format_date


@rest_controller("/stock")
class StockController:
    def __init__(self):
        super().__init__()
        self.database = SQLiteDatabase()

    @get_mapping("/list")
    def list_stocks(
        self,
        symbol: str = "",
        name: str = "",
        optional: Optional[int] = None,
        page_no: int = 1,
        page_size: int = 40,
    ):
        with RepositorySession(self.database) as session:
            stocks = session.stock_info.list_stock(
                symbol, name, optional, page_no, page_size
            )
            total = session.stock_info.count_stock(symbol, name, optional)
            return {"stocks": stocks, "total": total}

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

    @post_mapping("/optional")
    def optional(self, request: StockOptionalRequest) -> bool:
        stock_id = request.stock_id
        action = request.action
        with RepositorySession(self.database) as session:
            stock_info = session.stock_info.get(stock_id)
            if stock_info is None:
                return False
            if action == "add":
                session.stock_info.update(stock_id, optional=1)
            elif action == "remove":
                session.stock_info.update(stock_id, optional=0)
            else:
                raise ValueError(f"Invalid action: {action}")
            return True
