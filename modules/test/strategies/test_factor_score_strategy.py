from __future__ import annotations

import unittest
from datetime import date

import polars as pl

from modules.backtest.models import PortfolioState
from modules.core.context import Context
from modules.strategies.factor_score_strategy import FactorScoreStrategy
from modules.strategies.models import StrategyMeta


class _StubFactor:
    name = "stub_factor"
    version = "v1"
    value_type = "float"
    output_column = "stub_output"

    def __init__(self, params: dict | None = None) -> None:
        self.params = dict(params or {})

    def inputs(self) -> list[str]:
        return []

    def compute(self, context: Context) -> dict[str, pl.DataFrame]:
        return {
            "000001.SZ": pl.DataFrame(
                {
                    "instrument_id": ["000001.SZ", "000001.SZ"],
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "factor_value": [1.0, 2.0],
                }
            ),
            "600519.SH": pl.DataFrame(
                {
                    "instrument_id": ["600519.SH", "600519.SH"],
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "factor_value": [3.0, 4.0],
                }
            ),
        }


class FactorScoreStrategyBuildFactorFrameTest(unittest.TestCase):
    def test_build_factor_frame_uses_latest_factor_value_per_stock(self) -> None:
        factor = _StubFactor()

        result = FactorScoreStrategy._build_factor_frame(
            factor,
            Context(start_date="2024-01-01", end_date="2024-01-03"),
            "stub_factor_id",
        )

        self.assertEqual(
            result.sort("instrument_id").to_dict(as_series=False),
            {
                "instrument_id": ["000001.SZ", "600519.SH"],
                "stub_factor_id": [2.0, 4.0],
            },
        )


class FactorScoreStrategyDecideTest(unittest.TestCase):
    def test_decide_returns_equal_weight_targets(self) -> None:
        strategy = FactorScoreStrategy(
            meta=StrategyMeta(id=1, name="factor_score"),
            factors=[_StubFactor()],
            factor_weights={"stub_factor": 1.0},
            top_n_pct=1.0,
        )
        context = Context(
            start_date="2024-01-01",
            end_date="2024-01-03",
            stocks={
                "000001.SZ": object(),
                "600519.SH": object(),
            },
        )

        decision = strategy.decide(context, PortfolioState(as_of_date="2024-01-03"))

        self.assertEqual(decision.as_of_date, "2024-01-03")
        self.assertTrue(decision.close_missing_positions)
        self.assertEqual(
            [
                (target.instrument_id, target.target_weight)
                for target in decision.targets
            ],
            [("000001.SZ", 0.5), ("600519.SH", 0.5)],
        )


if __name__ == "__main__":
    unittest.main()
