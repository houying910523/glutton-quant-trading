from __future__ import annotations

from typing import Any

from modules.core import Filter
from modules.core.context import StockDailyData

# 只检查最近 3 个交易日。
WINDOW_SIZE = 3
# 按当前项目约定，turnover 字段直接表示换手率百分比。
TURNOVER_RATE_THRESHOLD = 0.05


class TurnoverFilter(Filter):
    """
    筛选最近 3 个交易日换手率都大于 5% 的股票。

    判断逻辑很直接：

    1. 只取最近 3 个交易日，不足 3 天直接排除。
    2. 读取最近 3 天的 turnover 字段。
    3. 按当前项目约定，turnover 直接作为“换手率百分比”使用。
    4. 只有当最近 3 天的换手率都严格大于 5.00 时，股票才会被保留。

    这里使用“最近 3 天都大于 5%”，而不是“3 天平均大于 5%”，
    是为了筛出近期连续活跃的标的，避免只靠某一天异常放量进入结果集。
    """

    name = "three_day_turnover_rate"
    params: dict[str, Any] = {}

    def dependencies(self) -> list[str]:
        return []

    def filter(self, data: list[StockDailyData]) -> list[StockDailyData]:
        return [item for item in data if self._matches(item)]

    @classmethod
    def _matches(cls, stock_daily_data: StockDailyData) -> bool:
        frame = stock_daily_data.data.sort("trade_date").tail(WINDOW_SIZE)
        if frame.height < WINDOW_SIZE:
            return False

        turnover_rates = frame["turnover"].to_list()
        # round(..., 2) 用来匹配“保留两位小数”的业务口径。
        # 任意一天 <= 5.00 或者缺失，都会被判定为不满足条件。
        return all(
            value is not None and round(float(value), 2) > TURNOVER_RATE_THRESHOLD
            for value in turnover_rates
        )
