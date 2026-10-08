from abc import abstractmethod, ABC
from typing import Any, Mapping

import polars as pl

from .context import Context, StockDailyData, ParamsProperty


class Factor(ABC):
    name: str
    version: str
    value_type: str
    output_column: str
    params_schema: list[ParamsProperty] = []

    def __init__(self, params: Mapping[str, Any] | None = None) -> None:
        self.params = params or {}

    @abstractmethod
    def inputs(self) -> list[str]: ...

    @abstractmethod
    def compute(self, context: Context) -> dict[str, pl.DataFrame]: ...

    @abstractmethod
    def matches(self, stock_daily_data: StockDailyData) -> bool: ...
