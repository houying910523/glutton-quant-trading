from datetime import timedelta

import polars as pl

from modules.core.context import StockDailyData
from modules.datasource.service.stock_daily_service import StockDailyService
from modules.filters import Filter
from modules.repositories.database import SQLiteDatabase
from modules.utils.time_util import now_shanghai

LOOKBACK_DAYS = 120


class Selection:
    """
    A selection of stocks based on a filter.
    """

    def __init__(
        self,
        database: SQLiteDatabase,
    ):
        self.database = database

    def run(
        self, filters: list[Filter], optional: bool = False
    ) -> list[StockDailyData]:
        """Run the selection."""
        stock_daily_service = StockDailyService(self.database)
        end_date = now_shanghai().date()
        start_date = end_date - timedelta(days=LOOKBACK_DAYS)
        data = stock_daily_service.load_stock_daily(
            start_date=start_date,
            end_date=end_date,
            optional=optional,
        )
        stock_daily_data = self._group_stock_daily_data(data)
        for _filter in filters:
            stock_daily_data = _filter.filter(stock_daily_data)
        return stock_daily_data

    @staticmethod
    def _group_stock_daily_data(data: pl.DataFrame) -> list[StockDailyData]:
        grouped_data = data.sort(["instrument_id", "trade_date"]).partition_by(
            "instrument_id",
            maintain_order=True,
        )
        return [
            StockDailyData(
                instrument_id=str(group["instrument_id"][0]),
                data=group,
            )
            for group in grouped_data
        ]
