from dataclasses import dataclass, field

import polars as pl

from modules.repositories.models import StockRecord


@dataclass(frozen=True)
class StockDailyData:
    instrument_id: str
    data: pl.DataFrame


@dataclass(frozen=True)
class Context:
    start_date: str
    end_date: str
    stock_daily_data: list[StockDailyData] = field(default_factory=list)
    stocks: dict[str, StockRecord] = field(default_factory=dict)
