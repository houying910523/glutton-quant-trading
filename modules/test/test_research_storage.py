from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

try:
    import polars as pl
except ModuleNotFoundError:  # pragma: no cover - optional at test runtime
    pl = None

from modules.utils.time_util import now_shanghai
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import (
    DailyQuoteRecord,
    IngestionBatchRecord,
    StockRecord,
)
from modules.repositories.schema import SQLiteSchemaManager


@unittest.skipIf(pl is None, "polars is not installed")
class ResearchStorageTest(unittest.TestCase):
    def test_sqlite_market_loader_loads_daily_bars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            SQLiteSchemaManager(database).initialize()
            self._seed_market_data(database)

            from modules.indicators.storage import SQLiteMarketLoader

            loader = SQLiteMarketLoader(database)
            frame = loader.load_daily_bars(
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 3),
                instruments=["600519.SH"],
                columns=["close", "volume", "turnover"],
            )

            self.assertEqual(
                frame.columns,
                ["trade_date", "instrument_id", "close", "volume", "turnover"],
            )
            self.assertEqual(frame.shape, (2, 5))
            self.assertEqual(
                frame["instrument_id"].to_list(), ["600519.SH", "600519.SH"]
            )
            self.assertEqual(frame["close"].to_list(), [10.2, 10.5])
            self.assertEqual(frame["volume"].to_list(), [1000, 1200])
            self.assertEqual(frame["turnover"].to_list(), [10200.0, 12600.0])

    def test_path_resolver_and_parquet_factor_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            from modules.indicators.storage import (
                IndicatorStore,
                resolve_dataset_root,
                resolve_partition_path,
            )

            root = Path(tmp_dir)
            indicator_root = root / "factors"
            store = IndicatorStore(indicator_root)
            storage_key = "ma/v1/window_20"

            dataset_root = resolve_dataset_root(indicator_root, storage_key)
            partition_path = resolve_partition_path(
                indicator_root,
                storage_key,
                year=2024,
                month=1,
            )

            self.assertEqual(dataset_root, indicator_root / "ma" / "v1" / "window_20")
            self.assertEqual(
                partition_path,
                indicator_root
                / "ma"
                / "v1"
                / "window_20"
                / "year=2024"
                / "month=01"
                / "data.parquet",
            )

            frame = pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "instrument_id": ["600519.SH", "600519.SH"],
                    "ma_20": [10.1, 10.2],
                }
            )
            written = store.write_month_partition(
                storage_key=storage_key,
                frame=frame,
                year=2024,
                month=1,
            )

            self.assertTrue(written.exists())
            self.assertTrue(store.exists(storage_key=storage_key))
            loaded = store.read_dataset(
                storage_key=storage_key, columns=["instrument_id", "ma_20"]
            )
            self.assertEqual(loaded.columns, ["instrument_id", "ma_20"])
            self.assertEqual(loaded.shape, (2, 2))
            self.assertEqual(loaded["ma_20"].to_list(), [10.1, 10.2])

    def _seed_market_data(self, database: SQLiteDatabase) -> None:
        now = now_shanghai()
        started_at = now.strftime("%Y-%m-%d %H:%M:%S")

        with RepositorySession(database, transactional=True) as repositories:
            repositories.stock.upsert_many(
                [
                    StockRecord(
                        market="CN",
                        exchange="SSE",
                        symbol="600519",
                        ticker="600519",
                        name="贵州茅台",
                        asset_type="stock",
                        currency="CNY",
                        lot_size=100,
                        listed_at=date(2001, 8, 27),
                        delisted_at=None,
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                ]
            )
            stock_row = repositories.stock.load_existing_by_natural_keys(
                [("CN", "SSE", "600519")]
            )
            stock_id = int(stock_row[("CN", "SSE", "600519")]["id"])

            batch = repositories.batch.create_batch(
                IngestionBatchRecord(
                    source_name="test",
                    resource_type="daily_quote",
                    sync_mode="incremental",
                    start_date="2024-01-02",
                    end_date="2024-01-03",
                    request_params={},
                    status="pending",
                    started_at=started_at,
                    created_at=started_at,
                    updated_at=started_at,
                )
            )

            repositories.daily_quote.upsert_many(
                [
                    DailyQuoteRecord(
                        stock_id=stock_id,
                        trade_date=date(2024, 1, 2),
                        open=1000,
                        high=1030,
                        low=990,
                        close=1020,
                        volume=1000,
                        turnover=1020000,
                        ingestion_batch_id=int(batch.id),
                        ingested_at=now,
                        updated_at=now,
                    ),
                    DailyQuoteRecord(
                        stock_id=stock_id,
                        trade_date=date(2024, 1, 3),
                        open=1020,
                        high=1060,
                        low=1010,
                        close=1050,
                        volume=1200,
                        turnover=1260000,
                        ingestion_batch_id=int(batch.id),
                        ingested_at=now,
                        updated_at=now,
                    ),
                ]
            )


if __name__ == "__main__":
    unittest.main()
