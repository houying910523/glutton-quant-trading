from abc import abstractmethod
from typing import Protocol

from modules.core.context import StockDailyData
from modules.strategies.models import StrategyMeta, Signal


class BaseStrategy(Protocol):
    def __init__(self, meta: StrategyMeta):
        self.meta: StrategyMeta = meta
        # 运行时状态
        self.signals: list[Signal] = []  # 本次产生的信号

    @abstractmethod
    def on_init(self):
        """策略初始化，引擎启动时调用一次"""
        pass

    @abstractmethod
    def on_bar(self, bar: StockDailyData):
        """K线到达回调，核心逻辑，产生Signal放到self.signals"""
        pass

    def get_signals(self) -> list[Signal]:
        """引擎获取策略产生的信号"""
        return self.signals
