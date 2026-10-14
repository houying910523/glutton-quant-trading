from __future__ import annotations

import unittest
from datetime import date

import polars as pl

from modules.backtest.models import PortfolioPosition, PortfolioState
from modules.core.context import Context, StockDailyData
from modules.strategies.factory import create_strategy
from modules.strategies.turtle_trading_strategy import TurtleTradingStrategy


def _daily_frame(
    instrument_id: str,
    *,
    high: list[float],
    low: list[float],
    close: list[float],
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trade_date": [date(2024, 1, day) for day in range(1, len(close) + 1)],
            "instrument_id": [instrument_id] * len(close),
            "high": high,
            "low": low,
            "close": close,
        }
    )


class TurtleTradingStrategyDecideTest(unittest.TestCase):
    def test_decide_enters_when_close_breaks_previous_high(self) -> None:
        strategy = TurtleTradingStrategy(
            entry_window=3,
            exit_window=2,
            atr_window=3,
            risk_pct=0.01,
            stop_atr_multiple=2.0,
        )
        context = Context(
            start_date="2024-01-01",
            end_date="2024-01-06",
            stock_daily_data=[
                StockDailyData(
                    instrument_id="000001.SZ",
                    data=_daily_frame(
                        "000001.SZ",
                        high=[10.0, 11.0, 12.0, 13.0, 14.0, 16.0],
                        low=[9.0, 10.0, 11.0, 12.0, 13.0, 14.0],
                        close=[9.5, 10.5, 11.5, 12.5, 13.5, 15.0],
                    ),
                )
            ],
        )

        decision = strategy.decide(context, PortfolioState(as_of_date="2024-01-06"))

        self.assertEqual(decision.as_of_date, "2024-01-06")
        self.assertFalse(decision.close_missing_positions)
        self.assertEqual(len(decision.targets), 1)
        self.assertEqual(decision.targets[0].instrument_id, "000001.SZ")
        self.assertGreater(decision.targets[0].target_weight, 0.0)
        self.assertIn("turtle_entry", decision.targets[0].reason)

    def test_decide_exits_when_close_breaks_previous_low(self) -> None:
        strategy = TurtleTradingStrategy(
            entry_window=3,
            exit_window=2,
            atr_window=2,
        )
        context = Context(
            start_date="2024-01-01",
            end_date="2024-01-05",
            stock_daily_data=[
                StockDailyData(
                    instrument_id="000001.SZ",
                    data=_daily_frame(
                        "000001.SZ",
                        high=[12.0, 12.0, 11.0, 10.0, 9.0],
                        low=[10.0, 10.0, 9.0, 8.8, 7.5],
                        close=[11.0, 11.0, 10.0, 9.5, 8.0],
                    ),
                )
            ],
        )
        portfolio_state = PortfolioState(
            as_of_date="2024-01-05",
            cash=200.0,
            positions={
                "000001.SZ": PortfolioPosition(
                    instrument_id="000001.SZ",
                    quantity=100,
                    available_quantity=100,
                    average_cost=10.0,
                    market_value=800.0,
                )
            },
        )

        decision = strategy.decide(context, portfolio_state)

        self.assertEqual(len(decision.targets), 1)
        self.assertEqual(decision.targets[0].instrument_id, "000001.SZ")
        self.assertEqual(decision.targets[0].target_weight, 0.0)
        self.assertIn("turtle_exit channel", decision.targets[0].reason)

    def test_decide_uses_smaller_weight_for_higher_atr(self) -> None:
        strategy = TurtleTradingStrategy(
            entry_window=3,
            exit_window=2,
            atr_window=3,
            risk_pct=0.01,
            stop_atr_multiple=2.0,
        )
        context = Context(
            start_date="2024-01-01",
            end_date="2024-01-06",
            stock_daily_data=[
                StockDailyData(
                    instrument_id="LOWATR.SZ",
                    data=_daily_frame(
                        "LOWATR.SZ",
                        high=[10.0, 11.0, 12.0, 13.0, 14.0, 16.0],
                        low=[9.0, 10.0, 11.0, 12.0, 13.0, 14.0],
                        close=[9.5, 10.5, 11.5, 12.5, 13.5, 15.0],
                    ),
                ),
                StockDailyData(
                    instrument_id="HIGHATR.SZ",
                    data=_daily_frame(
                        "HIGHATR.SZ",
                        high=[14.0, 14.0, 14.0, 14.0, 14.0, 22.0],
                        low=[6.0, 6.0, 6.0, 6.0, 6.0, 8.0],
                        close=[9.5, 10.5, 11.5, 12.5, 13.5, 15.0],
                    ),
                ),
            ],
        )

        decision = strategy.decide(context, PortfolioState(as_of_date="2024-01-06"))
        weights = {
            target.instrument_id: target.target_weight for target in decision.targets
        }

        self.assertLess(weights["HIGHATR.SZ"], weights["LOWATR.SZ"])


class TurtleTradingStrategyFactoryTest(unittest.TestCase):
    def test_create_strategy_returns_turtle_trading_strategy(self) -> None:
        strategy = create_strategy(
            "turtle_trading",
            {
                "instrument_ids": ["000001.SZ"],
                "entry_window": 5,
                "exit_window": 3,
                "atr_window": 4,
            },
        )

        self.assertIsInstance(strategy, TurtleTradingStrategy)
        self.assertEqual(strategy.meta.lookback_days, 8)


if __name__ == "__main__":
    unittest.main()
