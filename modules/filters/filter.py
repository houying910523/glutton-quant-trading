from abc import abstractmethod
from typing import Any, Protocol

from modules.core.context import StockDailyData, ParamsProperty


class Filter(Protocol):
    name: str
    params_schema: list[ParamsProperty] = []

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}

    def dependencies(self) -> list[str]:
        return []

    @abstractmethod
    def filter(self, data: list[StockDailyData]) -> list[StockDailyData]:
        """Return stocks using the recently daily data."""
        ...
