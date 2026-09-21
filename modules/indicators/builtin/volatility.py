from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from typing import Any

import polars as pl

from modules.indicators.base import Indicator
from modules.indicators.builtin.common import rolling_mean
from modules.indicators.models import IndicatorSpec


def _rolling_std(values: Sequence[float | None], window: int) -> list[float | None]:
    result: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < window:
            result.append(None)
            continue
        current = values[idx + 1 - window : idx + 1]
        if any(value is None for value in current):
            result.append(None)
            continue
        numeric = [float(value) for value in current if value is not None]
        mean = sum(numeric) / window
        variance = sum((value - mean) ** 2 for value in numeric) / window
        result.append(sqrt(variance))
    return result


def _true_range(
    high_values: Sequence[float | None],
    low_values: Sequence[float | None],
    close_values: Sequence[float | None],
) -> list[float | None]:
    result: list[float | None] = []
    previous_close: float | None = None
    for high, low, close in zip(high_values, low_values, close_values, strict=False):
        current_close = None if close is None else float(close)
        if high is None or low is None:
            result.append(None)
            previous_close = current_close
            continue

        high_value = float(high)
        low_value = float(low)
        current_range = high_value - low_value
        if previous_close is None:
            result.append(current_range)
        else:
            result.append(
                max(
                    current_range,
                    abs(high_value - previous_close),
                    abs(low_value - previous_close),
                )
            )
        previous_close = current_close
    return result


def _wilder_moving_average(
    values: Sequence[float | None],
    window: int,
) -> list[float | None]:
    result: list[float | None] = []
    seed_values: list[float] = []
    previous: float | None = None

    for value in values:
        if value is None:
            result.append(previous)
            continue

        current = float(value)
        if previous is None:
            seed_values.append(current)
            if len(seed_values) < window:
                result.append(None)
                continue
            previous = sum(seed_values) / window
            result.append(previous)
            continue

        previous = ((previous * (window - 1)) + current) / window
        result.append(previous)

    return result


class BollingerBandIndicator(Indicator):
    def spec(self, params: dict[str, Any]) -> IndicatorSpec:
        window = int(params["window"])
        num_std = int(params["num_std"])
        suffix = f"{window}_{num_std}"
        return IndicatorSpec(
            required_columns=["close"],
            required_history_bars=window,
            output_columns=[
                f"boll_mid_{suffix}",
                f"boll_upper_{suffix}",
                f"boll_lower_{suffix}",
            ],
        )

    def compute(
        self,
        frame: pl.DataFrame,
        params: dict[str, Any],
    ) -> pl.DataFrame:
        window = int(params["window"])
        num_std = int(params["num_std"])
        mid_col, upper_col, lower_col = self.spec(params).output_columns

        def compute_group(group: pl.DataFrame) -> pl.DataFrame:
            sorted_group = group.sort("trade_date")
            close = sorted_group["close"].to_list()
            middle = rolling_mean(close, window)
            std = _rolling_std(close, window)
            upper = [
                None if m is None or s is None else m + num_std * s
                for m, s in zip(middle, std, strict=False)
            ]
            lower = [
                None if m is None or s is None else m - num_std * s
                for m, s in zip(middle, std, strict=False)
            ]
            return sorted_group.select(
                "trade_date",
                "instrument_id",
                pl.Series(mid_col, middle),
                pl.Series(upper_col, upper),
                pl.Series(lower_col, lower),
            )

        return (
            frame.sort(["instrument_id", "trade_date"])
            .group_by("instrument_id", maintain_order=True)
            .map_groups(compute_group)
            .sort(["trade_date", "instrument_id"])
        )


class AverageTrueRangeIndicator(Indicator):
    def spec(self, params: dict[str, Any]) -> IndicatorSpec:
        window = int(params["window"])
        if window <= 0:
            raise ValueError("window must be > 0")
        return IndicatorSpec(
            required_columns=["high", "low", "close"],
            required_history_bars=max(window * 2, window + 1),
            output_columns=[f"atr_{window}"],
        )

    def compute(
        self,
        frame: pl.DataFrame,
        params: dict[str, Any],
    ) -> pl.DataFrame:
        window = int(params["window"])
        atr_col = self.spec(params).output_columns[0]

        def compute_group(group: pl.DataFrame) -> pl.DataFrame:
            sorted_group = group.sort("trade_date")
            high = sorted_group["high"].to_list()
            low = sorted_group["low"].to_list()
            close = sorted_group["close"].to_list()
            tr = _true_range(high, low, close)
            atr = _wilder_moving_average(tr, window)
            return sorted_group.select(
                "trade_date",
                "instrument_id",
                pl.Series(atr_col, atr),
            )

        return (
            frame.sort(["instrument_id", "trade_date"])
            .group_by("instrument_id", maintain_order=True)
            .map_groups(compute_group)
            .sort(["trade_date", "instrument_id"])
        )
