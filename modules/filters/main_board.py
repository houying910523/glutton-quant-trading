from __future__ import annotations

from modules.core.context import StockDailyData
from modules.filters.filter import Filter

SH_MAIN_BOARD_PREFIXES = ("600", "601", "603", "605")
SZ_MAIN_BOARD_PREFIXES = ("000", "001", "002", "003")


class MainBoardFilter(Filter):
    """
    只保留沪深主板股票。

    当前实现直接基于 `instrument_id` 判断，适合作为其他技术型 Filter 的前置过滤：

    - 上海主板：`600/601/603/605` 开头且后缀为 `.SH`
    - 深圳主板：`000/001/002/003` 开头且后缀为 `.SZ`
    - 创业板：`300*.SZ` 排除
    - 科创板：`688*.SH` 排除

    由于当前 Filter 接口没有直接暴露板块字段，因此这里不依赖 `stock_info`
    的额外标签，而是使用 A 股常见代码规则做静态过滤。
    """

    name = "main_board"

    def dependencies(self) -> list[str]:
        return []

    def filter(self, data: list[StockDailyData]) -> list[StockDailyData]:
        return [item for item in data if self._matches(item.instrument_id)]

    @classmethod
    def _matches(cls, instrument_id: str) -> bool:
        if not instrument_id or "." not in instrument_id:
            return False

        symbol, exchange = instrument_id.split(".", 1)
        if len(symbol) != 6 or not symbol.isdigit():
            return False

        if exchange == "SH":
            return symbol.startswith(SH_MAIN_BOARD_PREFIXES)
        if exchange == "SZ":
            return symbol.startswith(SZ_MAIN_BOARD_PREFIXES)
        return False
