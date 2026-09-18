from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
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
class RefreshFactorsTest(unittest.TestCase):
    def test_refresh_factors_materializes_month_partition(self) -> None:
        from modules.factors.refresh_factors import refresh_factors
        from modules.factors.storage import ParquetFactorStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            factor_root = root / "research" / "factors"
            SQLiteSchemaManager(database).initialize()
            self._seed_market_data(database)

            results = refresh_factors(
                database,
                factor_root,
                factor_ids=["ma_20"],
                start_date=date(2024, 1, 25),
                end_date=date(2024, 1, 25),
                instruments=["600519.SH"],
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["factor_id"], "ma_20")
            self.assertEqual(results[0]["rows_written"], 25)
            self.assertEqual(len(results[0]["partitions_written"]), 1)
            self.assertEqual(results[0]["last_materialized_date"], "2024-01-25")

            with RepositorySession(database) as repositories:
                definition = repositories.factor_definition.get("ma_20")

            self.assertIsNotNone(definition)
            assert definition is not None
            self.assertEqual(definition.last_materialized_date, "2024-01-25")

            store = ParquetFactorStore(factor_root)
            frame = store.read_dataset(storage_key="ma/v1/window_20")
            self.assertEqual(frame.height, 25)

            latest = frame.filter(
                (pl.col("trade_date") == pl.lit(date(2024, 1, 25)))
                & (pl.col("instrument_id") == pl.lit("600519.SH"))
            )
            self.assertEqual(latest.height, 1)
            self.assertAlmostEqual(float(latest["ma_20"][0]), 15.5)

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
                    start_date="2024-01-01",
                    end_date="2024-01-25",
                    request_params={},
                    status="pending",
                    started_at=started_at,
                    created_at=started_at,
                    updated_at=started_at,
                )
            )

            daily_quotes: list[DailyQuoteRecord] = []
            for offset in range(25):
                trade_date = date(2024, 1, 1) + timedelta(days=offset)
                close = (offset + 1) * 100
                daily_quotes.append(
                    DailyQuoteRecord(
                        stock_id=stock_id,
                        trade_date=trade_date,
                        open=close,
                        high=close + 10,
                        low=max(close - 10, 1),
                        close=close,
                        volume=1000 + offset,
                        turnover=close * (1000 + offset),
                        ingestion_batch_id=int(batch.id),
                        ingested_at=now,
                        updated_at=now,
                    )
                )

            repositories.daily_quote.upsert_many(daily_quotes)


if __name__ == "__main__":
    unittest.main()
