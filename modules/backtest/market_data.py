from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from modules.backtest.rules import DEFAULT_MARKET_RULES, MarketRules
from modules.utils.time_util import format_date

DailyBarLookupMap = dict[tuple[str, str], dict[str, float | None]]


def to_float(value: object) -> float | None:
    """把行情字段转换为浮点数；无法转换时视为缺失值。"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class DailyBarLookup:
    """按交易日和标的快速查询日线行情，并封装涨跌停判断。"""

    bars: DailyBarLookupMap
    rules: MarketRules = DEFAULT_MARKET_RULES

    @classmethod
    def from_frame(
        cls,
        market_data: pl.DataFrame,
        *,
        rules: MarketRules = DEFAULT_MARKET_RULES,
    ) -> "DailyBarLookup":
        """从日线 DataFrame 构造查询表，并为每条记录补入前收盘价。"""
        if market_data.is_empty():
            return cls({}, rules=rules)
        lookup: DailyBarLookupMap = {}
        previous_close_by_instrument: dict[str, float] = {}
        rows = market_data.sort(["instrument_id", "trade_date"]).to_dicts()
        for row in rows:
            trade_date = format_date(row.get("trade_date"))
            instrument_id = str(row.get("instrument_id"))
            if trade_date is None or not instrument_id:
                continue

            close_price = to_float(row.get("close"))
            lookup[(trade_date, instrument_id)] = {
                "open": to_float(row.get("open")),
                "high": to_float(row.get("high")),
                "low": to_float(row.get("low")),
                "close": close_price,
                "prev_close": previous_close_by_instrument.get(instrument_id),
            }
            if close_price is not None and close_price > 0:
                previous_close_by_instrument[instrument_id] = close_price
        return cls(lookup, rules=rules)

    def price(self, trade_date: str, instrument_id: str, field: str) -> float | None:
        """读取指定交易日、标的和字段的价格。"""
        bar = self.bar(trade_date, instrument_id)
        if bar is None:
            return None
        value = bar.get(field)
        return float(value) if value is not None else None

    def bar(
        self,
        trade_date: str,
        instrument_id: str,
    ) -> dict[str, float | None] | None:
        """读取指定交易日和标的的完整日线记录。"""
        return self.bars.get((trade_date, instrument_id))

    def is_limit_blocked(
        self,
        *,
        trade_date: str,
        instrument_id: str,
        side: str,
    ) -> bool:
        """判断开盘价是否触发涨跌停约束，导致对应方向无法成交。"""
        bar = self.bar(trade_date, instrument_id)
        if bar is None:
            return False

        open_price = to_float(bar.get("open"))
        prev_close = to_float(bar.get("prev_close"))
        if open_price is None or prev_close is None or prev_close <= 0:
            return False

        change_ratio = open_price / prev_close - 1.0
        if side == "buy" and change_ratio >= self.rules.limit_move_threshold:
            return True
        if side == "sell" and change_ratio <= -self.rules.limit_move_threshold:
            return True
        return False
