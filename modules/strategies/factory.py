from __future__ import annotations

from typing import Any

from modules.strategies.base import BaseStrategy
from modules.strategies.buy_and_hold_strategy import BuyAndHoldStrategy
from modules.strategies.turtle_trading_strategy import TurtleTradingStrategy


def create_strategy(strategy_id: str, strategy_params: dict[str, Any]) -> BaseStrategy:
    """按策略 ID 构造策略实例。"""
    if strategy_id == "buy_and_hold":
        instrument_ids = strategy_params.get("instrument_ids")
        if instrument_ids is not None and not isinstance(instrument_ids, list):
            raise ValueError("instrument_ids must be a list")
        return BuyAndHoldStrategy(
            instrument_ids=instrument_ids,
            total_weight=float(strategy_params.get("total_weight", 1.0)),
        )
    if strategy_id == "turtle_trading":
        instrument_ids = strategy_params.get("instrument_ids")
        if instrument_ids is not None and not isinstance(instrument_ids, list):
            raise ValueError("instrument_ids must be a list")
        return TurtleTradingStrategy(
            instrument_ids=instrument_ids,
            entry_window=int(strategy_params.get("entry_window", 20)),
            exit_window=int(strategy_params.get("exit_window", 10)),
            atr_window=int(strategy_params.get("atr_window", 20)),
            risk_pct=float(strategy_params.get("risk_pct", 0.01)),
            stop_atr_multiple=float(strategy_params.get("stop_atr_multiple", 2.0)),
            max_total_weight=float(strategy_params.get("max_total_weight", 1.0)),
        )
    raise ValueError(f"unsupported strategy_id: {strategy_id}")
