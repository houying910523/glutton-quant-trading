from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from modules.core.context import StockDailyData


def _build_stock_daily_data(
    instrument_id: str,
    *,
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    turnover_rates: list[float] | None = None,
) -> StockDailyData:
    assert pl is not None

    if highs is None:
        highs = [value + 1.0 for value in closes]
    if lows is None:
        lows = [value - 1.0 for value in closes]
    if turnover_rates is None:
        turnover_rates = [1.0] * len(closes)

    trade_dates = [
        date(2024, 1, 1) + timedelta(days=index) for index in range(len(closes))
    ]
    return StockDailyData(
        instrument_id=instrument_id,
        data=pl.DataFrame(
            {
                "trade_date": trade_dates,
                "close": closes,
                "high": highs,
                "low": lows,
                "turnover": turnover_rates,
            }
        ),
    )
