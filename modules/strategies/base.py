from abc import abstractmethod
from typing import Protocol

from modules.backtest.models import PortfolioState
from modules.core.context import Context
from modules.strategies.models import StrategyDecision, StrategyMeta


class BaseStrategy(Protocol):
    """策略核心接口，适合回测 / 模拟盘 / 实盘共用同一套决策逻辑。"""

    def __init__(self, meta: StrategyMeta):
        self.meta = meta

    @abstractmethod
    def decide(
        self,
        context: Context,
        portfolio_state: "PortfolioState",
    ) -> StrategyDecision:
        """基于当前可见数据与真实组合状态，输出目标仓位建议。"""
        pass
