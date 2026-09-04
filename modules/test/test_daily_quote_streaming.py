from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.datasource.pipeline.raw_store import RawStore
from modules.datasource.pipeline.services import DailyQuotePipeline
from modules.datasource.shared import FetchRequest, RawRecord, now_shanghai, parse_date
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import StockRecord, TradingCalendarRecord
from modules.repositories.schema import SQLiteSchemaManager


class TrackingDailyQuotePipeline(DailyQuotePipeline):
    def __init__(self, database: SQLiteDatabase, raw_store: RawStore) -> None:
        super().__init__(database, raw_store)
        self.upsert_sizes: list[int] = []

    def _upsert_records(self, repositories, records):
        self.upsert_sizes.append(len(records))
        super()._upsert_records(repositories, records)


class DailyQuoteStreamingTest(unittest.TestCase):
    def test_execute_stream_upserts_each_symbol_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            SQLiteSchemaManager(database).initialize()
            raw_store = RawStore(root / "raw")
            pipeline = TrackingDailyQuotePipeline(database, raw_store)
            now = now_shanghai()
            request = FetchRequest(
                resource_type="daily_quote",
                sync_mode="incremental",
                start_date="2024-08-26",
                end_date="2024-08-26",
                symbols=["600519", "000001"],
                trade_date="2024-08-26",
            )
            with RepositorySession(database, transactional=True) as repositories:
                repositories.stock.upsert_many(
                    [
                        StockRecord(
                            id=None,
                            market="CN",
                            exchange="SSE",
                            symbol="600519",
                            ticker="600519",
                            name="贵州茅台",
                            asset_type="stock",
                            currency="CNY",
                            lot_size=100,
                            listed_at=None,
                            delisted_at=None,
                            status="active",
                            created_at=now,
                            updated_at=now,
                        ),
                        StockRecord(
                            id=None,
                            market="CN",
                            exchange="SZSE",
                            symbol="000001",
                            ticker="000001",
                            name="平安银行",
                            asset_type="stock",
                            currency="CNY",
                            lot_size=100,
                            listed_at=None,
                            delisted_at=None,
                            status="active",
                            created_at=now,
                            updated_at=now,
                        ),
                    ]
                )
                repositories.trading_calendar.upsert_many(
                    [
                        TradingCalendarRecord(
                            id=None,
                            market="CN",
                            trade_date=parse_date("2024-08-26"),
                            is_open=True,
                            created_at=now,
                            updated_at=now,
                        )
                    ]
                )
                batch = repositories.batch.create_batch(
                    source_name="akshare",
                    request=request,
                )
                repositories.batch.mark_running(batch.id)
            batch = batch.model_copy(update={"status": "running"})

            chunks = [
                [
                    RawRecord(
                        ingestion_batch_id=batch.id,
                        source_name="akshare",
                        resource_type="daily_quote",
                        source_record_key="sh600519:2024-08-26",
                        fetched_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                        payload={
                            "date": "2024-08-26",
                            "open": 10.0,
                            "close": 10.2,
                            "high": 10.3,
                            "low": 9.9,
                            "volume": 123456,
                            "amount": 7890000.0,
                            "_market_symbol": "sh600519",
                            "_symbol": "600519",
                            "_exchange": "SSE",
                        },
                    )
                ],
                [
                    RawRecord(
                        ingestion_batch_id=batch.id,
                        source_name="akshare",
                        resource_type="daily_quote",
                        source_record_key="sz000001:2024-08-26",
                        fetched_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                        payload={
                            "date": "2024-08-26",
                            "open": 20.0,
                            "close": 20.2,
                            "high": 20.3,
                            "low": 19.9,
                            "volume": 223456,
                            "amount": 8890000.0,
                            "_market_symbol": "sz000001",
                            "_symbol": "000001",
                            "_exchange": "SZSE",
                        },
                    )
                ],
            ]

            result = pipeline.execute_stream(batch, request, chunks)

            self.assertEqual(result.status, "success")
            self.assertEqual(result.row_count_loaded, 2)
            self.assertEqual(pipeline.upsert_sizes, [1, 1])
            with RepositorySession(database) as repositories:
                self.assertEqual(
                    repositories.daily_quote.list_loaded_trade_dates(
                        start_date="2024-08-26",
                        end_date="2024-08-26",
                    ),
                    {"2024-08-26"},
                )


if __name__ == "__main__":
    unittest.main()
