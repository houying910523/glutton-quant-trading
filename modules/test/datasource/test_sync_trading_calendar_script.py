from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import typer

from modules.datasource.scripts.sync_trading_calendar import _resolve_date_range
from modules.utils.time_util import SHANGHAI_TZ


class ResolveDateRangeTest(unittest.TestCase):
    @patch("modules.datasource.scripts.sync_trading_calendar.RepositorySession")
    def test_resolve_date_range_returns_explicit_range_without_querying_database(
        self,
        mock_repository_session,
    ) -> None:
        result = _resolve_date_range(
            MagicMock(),
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

        self.assertEqual(result, ("2026-01-01", "2026-01-31"))
        mock_repository_session.assert_not_called()

    @patch("modules.datasource.scripts.sync_trading_calendar.now_shanghai")
    @patch("modules.datasource.scripts.sync_trading_calendar.RepositorySession")
    def test_resolve_date_range_uses_latest_stored_date_when_args_missing(
        self,
        mock_repository_session,
        mock_now_shanghai,
    ) -> None:
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = None
        session.trading_calendar.get_latest_trade_date.return_value = "2026-10-20"
        mock_repository_session.return_value = session
        mock_now_shanghai.return_value = datetime(2026, 10, 26, tzinfo=SHANGHAI_TZ)

        result = _resolve_date_range(
            MagicMock(),
            start_date=None,
            end_date=None,
        )

        self.assertEqual(result, ("2026-10-20", "2026-10-26"))

    @patch("modules.datasource.scripts.sync_trading_calendar.RepositorySession")
    def test_resolve_date_range_requires_explicit_range_without_existing_calendar(
        self,
        mock_repository_session,
    ) -> None:
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = None
        session.trading_calendar.get_latest_trade_date.return_value = None
        mock_repository_session.return_value = session

        with self.assertRaisesRegex(typer.BadParameter, "--start-date"):
            _resolve_date_range(MagicMock(), start_date=None, end_date=None)


if __name__ == "__main__":
    unittest.main()
