from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from modules.datasource.pipeline.stock_daily import (
    StockDailyPipeline,
    StockSyncTarget,
    Task,
)


class DailyQuotePipelineIncrementalTest(unittest.TestCase):
    @patch("modules.datasource.pipeline.stock_daily.now_shanghai")
    def test_incremental_daily_quote_syncs_full_history_for_symbol_without_dates(
        self,
        mock_now_shanghai,
    ) -> None:
        mock_now_shanghai.return_value = datetime(2024, 8, 29, 15, 0, 0)
        repositories = self._make_repositories(
            latest_trade_date=None,
            open_trade_dates=["2024-08-26", "2024-08-27", "2024-08-29"],
        )

        tasks = StockDailyPipeline._incremental_daily_quote(
            repositories,
            [
                StockSyncTarget(
                    stock_id=1,
                    symbol="600519",
                    listed_at="2024-08-26",
                    force=False,
                )
            ],
        )

        self.assertEqual(
            tasks,
            [
                Task(
                    stock_id=1,
                    symbol="600519",
                    history_start_date="2024-08-26",
                    start_date="2024-08-26",
                    end_date="2024-08-29",
                )
            ],
        )

    @patch("modules.datasource.pipeline.stock_daily.now_shanghai")
    def test_incremental_daily_quote_starts_from_next_day_for_existing_stock_id(
        self,
        mock_now_shanghai,
    ) -> None:
        mock_now_shanghai.return_value = datetime(2024, 8, 29, 15, 0, 0)
        repositories = self._make_repositories(
            latest_trade_date="2024-08-27",
            open_trade_dates=["2024-08-28", "2024-08-29"],
        )

        tasks = StockDailyPipeline._incremental_daily_quote(
            repositories,
            [
                StockSyncTarget(
                    stock_id=1,
                    symbol="600519",
                    listed_at="2024-08-26",
                    force=False,
                )
            ],
        )

        self.assertEqual(
            tasks,
            [
                Task(
                    stock_id=1,
                    symbol="600519",
                    history_start_date="2024-08-26",
                    start_date="2024-08-28",
                    end_date="2024-08-29",
                )
            ],
        )

    @patch("modules.datasource.pipeline.stock_daily.now_shanghai")
    def test_incremental_daily_quote_continues_from_latest_day_even_if_gap_exists(
        self,
        mock_now_shanghai,
    ) -> None:
        mock_now_shanghai.return_value = datetime(2024, 8, 29, 15, 0, 0)
        repositories = self._make_repositories(
            latest_trade_date="2024-08-28",
            open_trade_dates=["2024-08-29"],
        )

        tasks = StockDailyPipeline._incremental_daily_quote(
            repositories,
            [
                StockSyncTarget(
                    stock_id=1,
                    symbol="600519",
                    listed_at="2024-08-26",
                    force=False,
                )
            ],
        )

        self.assertEqual(
            tasks,
            [
                Task(
                    stock_id=1,
                    symbol="600519",
                    history_start_date="2024-08-26",
                    start_date="2024-08-29",
                    end_date="2024-08-29",
                )
            ],
        )

    @classmethod
    def _make_repositories(
        cls,
        *,
        latest_trade_date: str | None,
        open_trade_dates: list[str],
    ) -> MagicMock:
        repositories = MagicMock()
        repositories.stock_daily.get_latest_trade_date.return_value = latest_trade_date
        repositories.trading_calendar.list_open_trade_dates.return_value = (
            open_trade_dates
        )
        return repositories


if __name__ == "__main__":
    unittest.main()
