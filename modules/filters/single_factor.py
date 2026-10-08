from modules.core import Factor
from modules.filters.filter import Filter
from modules.core.context import StockDailyData


class SingleFactorFilter(Filter):
    def __init__(self) -> None:
        super().__init__()
        self.factor: Factor | None = None

    def filter(self, data: list[StockDailyData]) -> list[StockDailyData]:
        pass
