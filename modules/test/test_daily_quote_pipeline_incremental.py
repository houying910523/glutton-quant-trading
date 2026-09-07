from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.datasource.pipeline.raw_store import RawStore
from modules.datasource.pipeline.services.daily_quote import DailyQuotePipeline
from modules.datasource.shared import (
    format_timestamp,
    now_shanghai,
    parse_date,
)
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import (
    DailyQuoteRecord,
    IngestionBatchRecord,
    StockRecord,
    TradingCalendarRecord,
)
from modules.repositories.schema import SQLiteSchemaManager


class FakeDailyQuoteFetcher:
    def __init__(self, trade_dates_by_symbol: dict[str, list[str]]) -> None:
        self.trade_dates_by_symbol = trade_dates_by_symbol
        self.calls: list[tuple[str, str, str, int, int]] = []

    def fetch(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        stock_id: int,
        batch_id: int,
    ) -> list[DailyQuoteRecord]:
        self.calls.append((symbol, start_date, end_date, stock_id, batch_id))
        now = now_shanghai()
        return [
            DailyQuoteRecord(
                id=None,
                stock_id=stock_id,
                trade_date=parse_date(trade_date),
                open=1000,
                high=1010,
                low=990,
                close=1005,
                volume=100000,
                turnover=100000000,
                ingestion_batch_id=batch_id,
                ingested_at=now,
                updated_at=now,
            )
            for trade_date in self.trade_dates_by_symbol.get(symbol, [])
            if start_date <= trade_date <= end_date
        ]


class DailyQuotePipelineIncrementalTest(unittest.TestCase):
    def test_run_syncs_full_history_for_symbol_without_dates(self) -> None:
        with self._context() as ctx:
            stock_id = self._seed_stock(
                ctx.database,
                symbol="600519",
                listed_at="2024-08-26",
            )
            self._seed_calendar(
                ctx.database,
                ["2024-08-26", "2024-08-27", "2024-08-29"],
            )
            fetcher = FakeDailyQuoteFetcher(
                {"600519": ["2024-08-26", "2024-08-27", "2024-08-29"]}
            )

            with patch(
                "modules.datasource.adaptors.base.create_stock_daily_quote_fetcher",
                return_value=fetcher,
            ):
                result = ctx.pipeline.run("akshare", symbol="600519")

            self.assertEqual(result.status, "success")
            self.assertEqual(result.sync_mode, "incremental")
            self.assertEqual(result.loaded_count, 3)
            self.assertEqual(len(fetcher.calls), 1)
            self.assertEqual(
                fetcher.calls[0][:4], ("600519", "2024-08-26", "2024-08-29", stock_id)
            )
            with RepositorySession(ctx.database) as repositories:
                self.assertEqual(
                    repositories.daily_quote.list_trade_dates_by_stock(
                        stock_id=stock_id,
                        start_date="2024-08-26",
                        end_date="2024-08-29",
                    ),
                    ["2024-08-26", "2024-08-27", "2024-08-29"],
                )

    def test_run_starts_from_next_day_for_existing_stock_id(self) -> None:
        with self._context() as ctx:
            stock_id = self._seed_stock(
                ctx.database,
                symbol="600519",
                listed_at="2024-08-26",
            )
            self._seed_calendar(
                ctx.database,
                ["2024-08-26", "2024-08-27", "2024-08-28", "2024-08-29"],
            )
            self._seed_existing_quotes(
                ctx.database,
                stock_id=stock_id,
                trade_dates=["2024-08-26", "2024-08-27"],
            )
            fetcher = FakeDailyQuoteFetcher({"600519": ["2024-08-28", "2024-08-29"]})

            with patch(
                "modules.datasource.adaptors.base.create_stock_daily_quote_fetcher",
                return_value=fetcher,
            ):
                result = ctx.pipeline.run("akshare", stock_id=stock_id)

            self.assertEqual(result.status, "success")
            self.assertEqual(result.loaded_count, 2)
            self.assertEqual(len(fetcher.calls), 1)
            self.assertEqual(
                fetcher.calls[0][:4], ("600519", "2024-08-28", "2024-08-29", stock_id)
            )
            with RepositorySession(ctx.database) as repositories:
                self.assertEqual(
                    repositories.daily_quote.list_trade_dates_by_stock(
                        stock_id=stock_id,
                        start_date="2024-08-26",
                        end_date="2024-08-29",
                    ),
                    ["2024-08-26", "2024-08-27", "2024-08-28", "2024-08-29"],
                )

    def test_run_continues_from_latest_day_even_if_older_history_has_gap(self) -> None:
        with self._context() as ctx:
            stock_id = self._seed_stock(
                ctx.database,
                symbol="600519",
                listed_at="2024-08-26",
            )
            self._seed_calendar(
                ctx.database,
                ["2024-08-26", "2024-08-27", "2024-08-28", "2024-08-29"],
            )
            self._seed_existing_quotes(
                ctx.database,
                stock_id=stock_id,
                trade_dates=["2024-08-26", "2024-08-28"],
            )
            fetcher = FakeDailyQuoteFetcher({"600519": ["2024-08-29"]})

            with patch(
                "modules.datasource.adaptors.base.create_stock_daily_quote_fetcher",
                return_value=fetcher,
            ):
                result = ctx.pipeline.run("akshare", symbol="600519")

            self.assertEqual(result.status, "success")
            self.assertEqual(result.loaded_count, 1)
            self.assertEqual(
                fetcher.calls,
                [("600519", "2024-08-29", "2024-08-29", stock_id, result.id)],
            )
            with RepositorySession(ctx.database) as repositories:
                self.assertEqual(
                    repositories.daily_quote.list_trade_dates_by_stock(
                        stock_id=stock_id,
                        start_date="2024-08-26",
                        end_date="2024-08-29",
                    ),
                    ["2024-08-26", "2024-08-28", "2024-08-29"],
                )

    def _seed_stock(
        self,
        database: SQLiteDatabase,
        *,
        symbol: str,
        listed_at: str,
    ) -> int:
        now = now_shanghai()
        with RepositorySession(database, transactional=True) as repositories:
            repositories.stock.upsert_many(
                [
                    StockRecord(
                        id=None,
                        market="CN",
                        exchange="SSE" if symbol.startswith("6") else "SZSE",
                        symbol=symbol,
                        ticker=symbol,
                        name=symbol,
                        asset_type="stock",
                        currency="CNY",
                        lot_size=100,
                        listed_at=parse_date(listed_at),
                        delisted_at=None,
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                ]
            )
            row = repositories.stock.load_existing_by_natural_keys(
                [("CN", "SSE" if symbol.startswith("6") else "SZSE", symbol)]
            )[("CN", "SSE" if symbol.startswith("6") else "SZSE", symbol)]
            return int(row["id"])

    def _seed_calendar(self, database: SQLiteDatabase, trade_dates: list[str]) -> None:
        now = now_shanghai()
        with RepositorySession(database, transactional=True) as repositories:
            repositories.trading_calendar.upsert_many(
                [
                    TradingCalendarRecord(
                        id=None,
                        market="CN",
                        trade_date=parse_date(trade_date),
                        is_open=True,
                        created_at=now,
                        updated_at=now,
                    )
                    for trade_date in trade_dates
                ]
            )

    def _seed_existing_quotes(
        self,
        database: SQLiteDatabase,
        *,
        stock_id: int,
        trade_dates: list[str],
    ) -> None:
        now = now_shanghai()
        with RepositorySession(database, transactional=True) as repositories:
            batch = repositories.batch.create_batch(
                IngestionBatchRecord(
                    source_name="seed",
                    resource_type="daily_quote",
                    sync_mode="incremental",
                    start_date=trade_dates[0],
                    end_date=trade_dates[-1],
                    request_params={},
                    status="pending",
                    started_at=format_timestamp(now),
                    finished_at=None,
                    created_at=format_timestamp(now),
                    updated_at=format_timestamp(now),
                )
            )
            repositories.daily_quote.upsert_many(
                [
                    DailyQuoteRecord(
                        id=None,
                        stock_id=stock_id,
                        trade_date=parse_date(trade_date),
                        open=1000,
                        high=1010,
                        low=990,
                        close=1005,
                        volume=100000,
                        turnover=100000000,
                        ingestion_batch_id=batch.id,
                        ingested_at=now,
                        updated_at=now,
                    )
                    for trade_date in trade_dates
                ]
            )

    def _context(self):
        class _Context:
            def __enter__(self):
                self.temp_dir = tempfile.TemporaryDirectory()
                root = Path(self.temp_dir.name)
                self.database = SQLiteDatabase(root / "glutton.db")
                SQLiteSchemaManager(self.database).initialize()
                self.pipeline = DailyQuotePipeline(
                    self.database, RawStore(root / "raw")
                )
                return self

            def __exit__(self, exc_type, exc, tb):
                self.temp_dir.cleanup()

        return _Context()


if __name__ == "__main__":
    unittest.main()
