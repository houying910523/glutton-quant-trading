from __future__ import annotations

from typing import Any

from modules.filters.filter import Filter
from modules.core.context import StockDailyData
from modules.factors.box_consolidation import BoxConsolidationMatchFactor


class BoxConsolidationFilter(Filter):
    """
    使用 MA5 平滑后的局部波峰/波谷回归线识别近期箱体震荡。

    当前实现遵循以下约束：
    1. 只看最近 40 个交易日对应的平滑窗口；
    2. 用 MA5 平滑序列识别局部波峰/波谷；
    3. 波峰和波谷各至少 2 个；
    4. 对波峰和波谷分别做线性回归，得到上沿和下沿；
    5. 上下沿在窗口内的首尾漂移比例都必须小于 8%；
    6. 箱体高度必须在 10% ~ 25% 之间；
    7. 最新收盘价仍在箱体内，或者最近 3 天至少 2 天仍在箱体内。
    """

    name = "box_consolidation"
    params_schema = BoxConsolidationMatchFactor.params_schema

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.factor = BoxConsolidationMatchFactor(self.params)

    def dependencies(self) -> list[str]:
        return self.factor.inputs()

    def filter(self, data: list[StockDailyData]) -> list[StockDailyData]:
        return [item for item in data if self.matches(item)]

    def matches(self, stock_daily_data: StockDailyData) -> bool:
        return self.factor.matches(stock_daily_data)
