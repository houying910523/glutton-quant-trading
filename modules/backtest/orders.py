from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduledOrder:
    """已排定在某个交易日执行的买卖指令。"""

    trade_date: str
    instrument_id: str
    side: str
    quantity: int
    requested_price: float | None = None
    reason: str = ""
