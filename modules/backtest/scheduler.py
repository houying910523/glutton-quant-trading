from __future__ import annotations

from collections import OrderedDict
from datetime import date


class RebalanceScheduler:
    """根据交易日历生成策略调仓日。"""

    SUPPORTED_FREQUENCIES = {"daily", "weekly", "monthly"}

    def build_rebalance_dates(
        self,
        trade_dates: list[str],
        frequency: str,
    ) -> list[str]:
        """按调仓频率返回实际可交易的调仓日期。"""
        if frequency not in self.SUPPORTED_FREQUENCIES:
            raise ValueError(f"unsupported rebalance frequency: {frequency}")
        if frequency == "daily":
            return list(trade_dates)
        if frequency == "weekly":
            return self._last_trade_date_per_week(trade_dates)
        return self._last_trade_date_per_month(trade_dates)

    @staticmethod
    def _last_trade_date_per_week(trade_dates: list[str]) -> list[str]:
        """返回每个自然周内最后一个开市日。"""
        buckets: OrderedDict[str, str] = OrderedDict()
        for trade_date in trade_dates:
            year, month, day = map(int, trade_date.split("-"))
            iso_year, iso_week, _ = date(year, month, day).isocalendar()
            buckets[f"{iso_year}-W{iso_week:02d}"] = trade_date
        return list(buckets.values())

    @staticmethod
    def _last_trade_date_per_month(trade_dates: list[str]) -> list[str]:
        """返回每个自然月内最后一个开市日。"""
        buckets: OrderedDict[str, str] = OrderedDict()
        for trade_date in trade_dates:
            buckets[trade_date[:7]] = trade_date
        return list(buckets.values())
