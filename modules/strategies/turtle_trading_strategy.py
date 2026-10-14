from __future__ import annotations

import math

import polars as pl

from modules.backtest.models import PortfolioPosition, PortfolioState
from modules.core.context import Context
from modules.indicators.builtin.volatility import AverageTrueRangeIndicator
from modules.strategies.base import BaseStrategy
from modules.strategies.models import StrategyDecision, StrategyMeta, TargetPosition


class TurtleTradingStrategy(BaseStrategy):
    """海龟交易最小研究版：通道突破入场，通道/ATR 止损退出。"""

    def __init__(
        self,
        instrument_ids: list[str] | None = None,
        *,
        entry_window: int = 20,
        exit_window: int = 10,
        atr_window: int = 20,
        risk_pct: float = 0.01,
        stop_atr_multiple: float = 2.0,
        max_total_weight: float = 1.0,
        meta: StrategyMeta | None = None,
    ) -> None:
        self.entry_window = self._positive_int(entry_window, "entry_window")
        self.exit_window = self._positive_int(exit_window, "exit_window")
        self.atr_window = self._positive_int(atr_window, "atr_window")
        self.risk_pct = self._positive_float(risk_pct, "risk_pct")
        self.stop_atr_multiple = self._positive_float(
            stop_atr_multiple,
            "stop_atr_multiple",
        )
        self.max_total_weight = self._max_total_weight(max_total_weight)
        self.instrument_ids = list(instrument_ids or [])
        lookback_days = max(
            self.entry_window + 1,
            self.exit_window + 1,
            self.atr_window * 2,
        )
        self.meta = meta or StrategyMeta(
            id=0,
            name="turtle_trading",
            description="Long-only Turtle trading strategy with ATR risk sizing.",
            lookback_days=lookback_days,
            inputs=["high", "low", "close"],
        )
        self._atr_indicator = AverageTrueRangeIndicator()

    def decide(
        self,
        context: Context,
        portfolio_state: PortfolioState,
    ) -> StrategyDecision:
        allowed = set(self.instrument_ids) if self.instrument_ids else None
        frames = {
            item.instrument_id: item.data
            for item in context.stock_daily_data
            if allowed is None or item.instrument_id in allowed
        }

        targets: list[TargetPosition] = []
        skipped_count = 0
        for instrument_id in sorted(frames):
            target = self._target_for_instrument(
                instrument_id=instrument_id,
                frame=frames[instrument_id],
                portfolio_state=portfolio_state,
            )
            if target is None:
                skipped_count += 1
                continue
            targets.append(target)

        targets = self._scale_targets(targets)
        return StrategyDecision(
            as_of_date=context.end_date,
            targets=targets,
            close_missing_positions=False,
            metadata={
                "selected_count": sum(
                    1 for target in targets if target.target_weight > 0
                ),
                "skipped_count": skipped_count,
            },
        )

    def _target_for_instrument(
        self,
        *,
        instrument_id: str,
        frame: pl.DataFrame,
        portfolio_state: PortfolioState,
    ) -> TargetPosition | None:
        self._validate_frame(frame, instrument_id)
        sorted_frame = frame.sort("trade_date")
        close = self._latest_float(sorted_frame, "close")
        if close is None or close <= 0:
            return None

        position = portfolio_state.positions.get(
            instrument_id,
            PortfolioPosition(instrument_id=instrument_id),
        )
        held = position.quantity > 0
        exit_low = self._previous_low(sorted_frame)
        atr = self._latest_atr(sorted_frame)

        if held:
            if exit_low is not None and close < exit_low:
                return TargetPosition(
                    instrument_id=instrument_id,
                    target_weight=0.0,
                    reason=f"turtle_exit channel close={close:.6f} exit_low={exit_low:.6f}",
                )
            if (
                atr is not None
                and position.average_cost > 0
                and close <= position.average_cost - self.stop_atr_multiple * atr
            ):
                return TargetPosition(
                    instrument_id=instrument_id,
                    target_weight=0.0,
                    reason=f"turtle_exit stop close={close:.6f} atr={atr:.6f}",
                )
            return TargetPosition(
                instrument_id=instrument_id,
                target_weight=self._current_weight(position, portfolio_state),
                reason="turtle_hold",
            )

        entry_high = self._previous_high(sorted_frame)
        if entry_high is None or atr is None or close <= entry_high:
            return None
        target_weight = self.risk_pct * close / (self.stop_atr_multiple * atr)
        if not math.isfinite(target_weight) or target_weight <= 0:
            return None
        return TargetPosition(
            instrument_id=instrument_id,
            target_weight=target_weight,
            reason=f"turtle_entry close={close:.6f} entry_high={entry_high:.6f} atr={atr:.6f}",
        )

    def _latest_atr(self, frame: pl.DataFrame) -> float | None:
        atr_col = f"atr_{self.atr_window}"
        atr_frame = self._atr_indicator.compute(frame, {"window": self.atr_window})
        if atr_frame.height == 0:
            return None
        value = atr_frame.sort("trade_date")[atr_col].to_list()[-1]
        if value is None:
            return None
        value = float(value)
        if value <= 0 or not math.isfinite(value):
            return None
        return value

    def _previous_high(self, frame: pl.DataFrame) -> float | None:
        if frame.height < self.entry_window + 1:
            return None
        values = (
            frame.tail(self.entry_window + 1).head(self.entry_window)["high"].to_list()
        )
        if any(value is None for value in values):
            return None
        return max(float(value) for value in values)

    def _previous_low(self, frame: pl.DataFrame) -> float | None:
        if frame.height < self.exit_window + 1:
            return None
        values = (
            frame.tail(self.exit_window + 1).head(self.exit_window)["low"].to_list()
        )
        if any(value is None for value in values):
            return None
        return min(float(value) for value in values)

    def _scale_targets(self, targets: list[TargetPosition]) -> list[TargetPosition]:
        total_weight = sum(target.target_weight for target in targets)
        if total_weight <= self.max_total_weight:
            return targets
        scale = self.max_total_weight / total_weight
        return [
            TargetPosition(
                instrument_id=target.instrument_id,
                target_weight=target.target_weight * scale,
                reason=f"{target.reason} scaled={scale:.6f}",
            )
            for target in targets
        ]

    @staticmethod
    def _current_weight(
        position: PortfolioPosition,
        portfolio_state: PortfolioState,
    ) -> float:
        if portfolio_state.total_equity <= 0:
            return 0.0
        return max(0.0, float(position.market_value) / portfolio_state.total_equity)

    @staticmethod
    def _latest_float(frame: pl.DataFrame, column: str) -> float | None:
        value = frame[column].to_list()[-1]
        return None if value is None else float(value)

    @staticmethod
    def _validate_frame(frame: pl.DataFrame, instrument_id: str) -> None:
        required = {"trade_date", "instrument_id", "high", "low", "close"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(
                f"turtle_trading missing columns for {instrument_id}: {sorted(missing)}"
            )

    @staticmethod
    def _positive_int(value: int, name: str) -> int:
        value = int(value)
        if value <= 0:
            raise ValueError(f"{name} must be > 0")
        return value

    @staticmethod
    def _positive_float(value: float, name: str) -> float:
        value = float(value)
        if value <= 0 or not math.isfinite(value):
            raise ValueError(f"{name} must be > 0")
        return value

    @staticmethod
    def _max_total_weight(value: float) -> float:
        value = float(value)
        if value <= 0 or value > 1.0 or not math.isfinite(value):
            raise ValueError("max_total_weight must be > 0 and <= 1")
        return value
