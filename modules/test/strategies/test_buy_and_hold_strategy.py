from __future__ import annotations

import unittest
from datetime import date

import polars as pl

from modules.backtest.models import PortfolioState
from modules.core.context import Context, StockDailyData
from modules.strategies.buy_and_hold_strategy import BuyAndHoldStrategy


class BuyAndHoldStrategyDecideTest(unittest.TestCase):
    def test_decide_returns_equal_weight_targets_from_configured_instruments(
        self,
    ) -> None:
        strategy = BuyAndHoldStrategy(
            instrument_ids=["000001.SZ", "600519.SH"],
            total_weight=0.8,
        )

        decision = strategy.decide(
            Context(start_date="2024-01-02", end_date="2024-01-03"),
            PortfolioState(as_of_date="2024-01-03"),
        )

        self.assertEqual(decision.as_of_date, "2024-01-03")
        self.assertTrue(decision.close_missing_positions)
        self.assertEqual(decision.metadata["selected_count"], 2)
        self.assertEqual(
            [
                (target.instrument_id, target.target_weight)
                for target in decision.targets
            ],
            [("000001.SZ", 0.4), ("600519.SH", 0.4)],
        )

    def test_decide_uses_context_stock_daily_data_when_instruments_not_configured(
        self,
    ) -> None:
        strategy = BuyAndHoldStrategy()

        decision = strategy.decide(
            Context(
                start_date="2024-01-02",
                end_date="2024-01-03",
                stock_daily_data=[
                    StockDailyData(
                        instrument_id="600519.SH",
                        data=pl.DataFrame(
                            {
                                "trade_date": [date(2024, 1, 3)],
                                "instrument_id": ["600519.SH"],
                                "close": [100.0],
                            }
                        ),
                    ),
                    StockDailyData(
                        instrument_id="000001.SZ",
                        data=pl.DataFrame(
                            {
                                "trade_date": [date(2024, 1, 3)],
                                "instrument_id": ["000001.SZ"],
                                "close": [10.0],
                            }
                        ),
                    ),
                ],
            ),
            PortfolioState(as_of_date="2024-01-03"),
        )

        self.assertEqual(
            [
                (target.instrument_id, target.target_weight)
                for target in decision.targets
            ],
            [("000001.SZ", 0.5), ("600519.SH", 0.5)],
        )


if __name__ == "__main__":
    unittest.main()
