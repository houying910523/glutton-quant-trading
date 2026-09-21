from abc import abstractmethod
from typing import Any, Mapping, Protocol

from modules.core.context import StockDailyData


class Filter(Protocol):
    name: str
    params: Mapping[str, Any]

    def dependencies(self) -> list[str]:
        return []

    @abstractmethod
    def filter(self, data: list[StockDailyData]) -> list[StockDailyData]:
        """Return stocks using the recently daily data."""
        ...
