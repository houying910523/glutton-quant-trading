from __future__ import annotations

import polars as pl

from modules.core import Factor
from modules.core.context import Context, StockDailyData
from modules.strategies.base import BaseStrategy
from modules.strategies.factor_processor import FactorProcessor
from modules.strategies.models import Signal, StrategyMeta


class FactorScoreStrategy(BaseStrategy):
    def __init__(
        self,
        meta: StrategyMeta,
        factors: list[Factor],
        factor_weights: dict[str, float],
        top_n_pct: float = 0.2,
    ) -> None:
        self.meta = meta
        self.signals: list[Signal] = []
        self.positions: dict[str, float] = {}
        self.factors: list[Factor] = factors
        self.factor_weights = factor_weights
        self.top_n_pct = top_n_pct
        self.processor = FactorProcessor()

    def on_init(self) -> None:
        print(
            f"多因子策略 [{self.meta.name}] 初始化完成，因子列表：{[f.name for f in self.factors]}"
        )

    def on_bar(self, bar: StockDailyData | Context) -> None:
        if not isinstance(bar, Context):
            raise TypeError("FactorScoreStrategy.on_bar expects a Context instance")

        context = bar
        self.signals = []

        symbols = list(context.stocks.keys())
        if not symbols:
            symbols = [item.instrument_id for item in context.stock_daily_data]
        df = pl.DataFrame({"instrument_id": symbols})

        for factor in self.factors:
            fid = self._factor_id(factor)
            factor_frame = self._build_factor_frame(factor, context, fid)
            df = df.join(factor_frame, on="instrument_id", how="left")

        for factor in self.factors:
            fid = self._factor_id(factor)
            if fid not in df.columns:
                raise ValueError(f"factor column not found: {fid}")

            series = df.get_column(fid).cast(pl.Float64, strict=False)
            series = self.processor.winsorize(series)
            series = self.processor.standardize(series)
            if self._factor_type(factor) == "negative":
                series = -series
            df = df.with_columns(series.alias(fid))

        score_expr = pl.lit(0.0)
        for factor in self.factors:
            fid = self._factor_id(factor)
            weight = self._factor_weight(factor)
            score_expr = score_expr + pl.col(fid) * pl.lit(weight)
        df = df.with_columns(score_expr.alias("score")).drop_nulls(["score"])

        selected_symbols: list[str] = []
        if df.height > 0:
            cutoff = df.get_column("score").quantile(1 - self.top_n_pct)
            if cutoff is not None:
                selected = df.filter(pl.col("score") >= float(cutoff))
                selected_symbols = selected.get_column("instrument_id").to_list()

        target_weight = 1.0 / len(selected_symbols) if selected_symbols else 0.0
        target_positions = {symbol: target_weight for symbol in selected_symbols}

        all_symbols = set(self.positions.keys()) | set(target_positions.keys())
        for symbol in sorted(all_symbols):
            old_weight = self.positions.get(symbol, 0.0)
            new_weight = target_positions.get(symbol, 0.0)
            if abs(new_weight - old_weight) < 1e-6:
                continue

            if new_weight > old_weight:
                signal = Signal(
                    symbol=symbol,
                    direction="long",
                    signal_type="open",
                    reason=f"factor_buy target_weight={new_weight:.6f}",
                )
            else:
                signal = Signal(
                    symbol=symbol,
                    direction="flat",
                    signal_type="close",
                    reason=f"factor_sell target_weight={new_weight:.6f}",
                )
            self.signals.append(signal)

        self.positions = target_positions

    @staticmethod
    def _factor_id(factor: Factor) -> str:
        return str(getattr(factor, "factor_id", factor.name))

    @staticmethod
    def _factor_type(factor: Factor) -> str:
        return str(getattr(factor, "factor_type", "positive"))

    def _factor_weight(self, factor: Factor) -> float:
        factor_id = self._factor_id(factor)
        if factor_id in self.factor_weights:
            return float(self.factor_weights[factor_id])
        if factor.name in self.factor_weights:
            return float(self.factor_weights[factor.name])
        raise KeyError(f"missing factor weight for factor: {factor_id}")

    @staticmethod
    def _build_factor_frame(
        factor: Factor, context: Context, factor_id: str
    ) -> pl.DataFrame:
        result = factor.compute(context)
        latest_rows: list[pl.DataFrame] = []
        for instrument_id, factor_frame in result.items():
            required_columns = {"instrument_id", "trade_date", "factor_value"}
            if not required_columns.issubset(set(factor_frame.columns)):
                raise ValueError(
                    f"factor result missing required columns for {factor_id}: {instrument_id}"
                )
            if factor_frame.height == 0:
                continue

            latest_rows.append(
                factor_frame.sort("trade_date")
                .tail(1)
                .select(
                    "instrument_id",
                    pl.col("factor_value").alias(factor_id),
                )
            )

        if not latest_rows:
            return pl.DataFrame(
                schema={
                    "instrument_id": pl.Utf8,
                    factor_id: pl.Float64,
                }
            )

        return pl.concat(latest_rows, how="vertical")
