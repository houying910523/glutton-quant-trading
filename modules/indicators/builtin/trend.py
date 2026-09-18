from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import polars as pl

from modules.indicators.base import Indicator
from modules.indicators.builtin.common import rolling_mean
from modules.indicators.models import IndicatorSpec


def _ema(values: Sequence[float | None], span: int) -> list[float | None]:
    alpha = 2.0 / (span + 1.0)
    result: list[float | None] = []
    previous: float | None = None
    for value in values:
        if value is None:
            result.append(previous)
            continue
        current = float(value)
        if previous is None:
            previous = current
        else:
            previous = alpha * current + (1.0 - alpha) * previous
        result.append(previous)
    return result


class SimpleMovingAverageIndicator(Indicator):
    def spec(self, params: dict[str, Any]) -> IndicatorSpec:
        window_list = params["window"]
        output_columns = [f"ma_{window}" for window in window_list]
        return IndicatorSpec(
            required_columns=["close"],
            required_history_bars=max(window_list),
            output_columns=output_columns,
        )

    def compute(
        self,
        frame: pl.DataFrame,
        params: dict[str, Any],
    ) -> pl.DataFrame:
        spec = self.spec(params)
        window_list = params["window"]
        output_columns = spec.output_columns

        def compute_group(group: pl.DataFrame) -> pl.DataFrame:
            sorted_group = group.sort("trade_date")
            values = sorted_group["close"].to_list()
            return sorted_group.select(
                "trade_date",
                "instrument_id",
                *[
                    pl.Series(col, rolling_mean(values, window))
                    for col, window in zip(output_columns, window_list)
                ],
            )

        return (
            frame.sort(["instrument_id", "trade_date"])
            .group_by("instrument_id", maintain_order=True)
            .map_groups(compute_group)
            .sort(["trade_date", "instrument_id"])
        )


class MacdIndicator(Indicator):
    def spec(self, params: dict[str, Any]) -> IndicatorSpec:
        fast = int(params["fast"])
        slow = int(params["slow"])
        signal = int(params["signal"])
        suffix = f"{fast}_{slow}_{signal}"
        return IndicatorSpec(
            required_columns=["close"],
            required_history_bars=max(slow + signal, slow * 2),
            output_columns=[
                f"macd_dif_{suffix}",
                f"macd_dea_{suffix}",
                f"macd_hist_{suffix}",
            ],
        )

    def compute(
        self,
        frame: pl.DataFrame,
        params: dict[str, Any],
    ) -> pl.DataFrame:
        fast = int(params["fast"])
        slow = int(params["slow"])
        signal = int(params["signal"])
        spec = self.spec(params)
        dif_col, dea_col, hist_col = spec.output_columns

        def compute_group(group: pl.DataFrame) -> pl.DataFrame:
            sorted_group = group.sort("trade_date")
            close = sorted_group["close"].to_list()
            ema_fast = _ema(close, fast)
            ema_slow = _ema(close, slow)
            dif = [
                None if f is None or s is None else f - s
                for f, s in zip(ema_fast, ema_slow, strict=False)
            ]
            dea = _ema(dif, signal)
            hist = [
                None if d is None or e is None else (d - e) * 2.0
                for d, e in zip(dif, dea, strict=False)
            ]
            return sorted_group.select(
                "trade_date",
                "instrument_id",
                pl.Series(dif_col, dif),
                pl.Series(dea_col, dea),
                pl.Series(hist_col, hist),
            )

        return (
            frame.sort(["instrument_id", "trade_date"])
            .group_by("instrument_id", maintain_order=True)
            .map_groups(compute_group)
            .sort(["trade_date", "instrument_id"])
        )
