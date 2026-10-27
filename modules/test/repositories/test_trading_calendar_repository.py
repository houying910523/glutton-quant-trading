from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import TradingCalendarRecord
from modules.repositories.schema import SQLiteSchemaManager
from modules.utils.time_util import now_shanghai


def _initialize_database(root: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(root / "glutton.db")
    SQLiteSchemaManager(database).initialize()
    return database


class TradingCalendarRepositoryGetLatestTradeDateTest(unittest.TestCase):
    def test_get_latest_trade_date_returns_latest_stored_calendar_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database = _initialize_database(Path(tmp_dir))
            now = now_shanghai()

            with RepositorySession(database, transactional=True) as repositories:
                repositories.trading_calendar.upsert_many(
                    [
                        TradingCalendarRecord(
                            id=None,
                            market="CN",
                            trade_date=date(2026, 10, 20),
                            is_open=True,
                            created_at=now,
                            updated_at=now,
                        ),
                        TradingCalendarRecord(
                            id=None,
                            market="CN",
                            trade_date=date(2026, 10, 26),
                            is_open=False,
                            created_at=now,
                            updated_at=now,
                        ),
                    ]
                )

            with RepositorySession(database) as repositories:
                latest_trade_date = (
                    repositories.trading_calendar.get_latest_trade_date()
                )

            self.assertEqual(latest_trade_date, "2026-10-26")


if __name__ == "__main__":
    unittest.main()
