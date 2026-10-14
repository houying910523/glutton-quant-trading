from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import polars as pl

from modules.backtest.engine import BacktestEngine
from modules.backtest.models import BacktestConfig
from modules.backtest.runner import BacktestRunner
from modules.datasource.service.stock_daily_service import StockDailyService
from modules.strategies.buy_and_hold_strategy import BuyAndHoldStrategy


class BacktestRunnerIntegrationTest(unittest.TestCase):
    @patch.object(StockDailyService, "load_stock_daily")
    @patch.object(BacktestEngine, "list_recent_trade_dates")
    @patch.object(BacktestEngine, "list_trade_dates")
    def test_run_completes_full_flow_with_buy_and_hold_strategy(
        self,
        mock_list_trade_dates,
        mock_list_recent_trade_dates,
        mock_load_stock_daily,
    ) -> None:
        mock_list_trade_dates.return_value = [
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
        ]
        mock_list_recent_trade_dates.side_effect = lambda *, end_date, limit: [
            end_date
        ][-limit:]
        mock_load_stock_daily.side_effect = self._load_stock_daily

        runner = BacktestRunner(database=object())
        artifact = runner.run(
            BuyAndHoldStrategy(instrument_ids=["000001.SZ"]),
            BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-04",
                initial_cash=1500.0,
                rebalance_frequency="daily",
                commission_rate=0.0,
                slippage_rate=0.0,
                instruments=["000001.SZ"],
            ),
        )

        result = artifact.result
        self.assertEqual(result.trade_dates, ["2024-01-02", "2024-01-03", "2024-01-04"])
        self.assertEqual(
            result.rebalance_dates, ["2024-01-02", "2024-01-03", "2024-01-04"]
        )
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.orders[0].side, "buy")
        self.assertEqual(result.orders[0].trade_date, "2024-01-03")
        self.assertEqual(result.orders[0].quantity, 100)
        self.assertAlmostEqual(result.final_portfolio_state.cash, 500.0)
        self.assertEqual(
            result.final_portfolio_state.positions["000001.SZ"].quantity, 100
        )
        self.assertEqual(
            [point.total_equity for point in result.equity_curve],
            [1500.0, 1600.0, 1700.0],
        )

        self.assertEqual(artifact.analysis.summary.fill_count, 1)
        self.assertAlmostEqual(artifact.analysis.summary.final_equity, 1700.0)
        self.assertEqual(artifact.analysis.metadata["equity_points"], 3)

    def _load_stock_daily(self, *args, **kwargs) -> pl.DataFrame:
        columns = kwargs.get("columns")
        if columns == ["open", "high", "low", "close"]:
            return pl.DataFrame(
                {
                    "trade_date": [
                        date(2024, 1, 2),
                        date(2024, 1, 3),
                        date(2024, 1, 4),
                    ],
                    "instrument_id": ["000001.SZ", "000001.SZ", "000001.SZ"],
                    "open": [10.0, 10.0, 12.0],
                    "high": [10.0, 11.0, 12.0],
                    "low": [10.0, 10.0, 12.0],
                    "close": [10.0, 11.0, 12.0],
                }
            )
        return pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 2)],
                "instrument_id": ["000001.SZ"],
                "close": [10.0],
            }
        )


if __name__ == "__main__":
    unittest.main()
