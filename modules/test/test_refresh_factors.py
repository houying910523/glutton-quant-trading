from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

try:
    import polars as pl
except ModuleNotFoundError:  # pragma: no cover - optional at test runtime
    pl = None

from modules.utils.time_util import format_timestamp, now_shanghai
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import (
    DailyQuoteRecord,
    FactorDefinitionRecord,
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

    def test_refresh_factors_resumes_from_last_materialized_month(self) -> None:
        from modules.factors.refresh_factors import refresh_factors
        from modules.factors.storage import ParquetFactorStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            factor_root = root / "research" / "factors"
            SQLiteSchemaManager(database).initialize()
            self._seed_market_data(
                database,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 10),
            )

            refresh_factors(
                database,
                factor_root,
                factor_ids=["ma_20"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                instruments=["600519.SH"],
            )
            results = refresh_factors(
                database,
                factor_root,
                factor_ids=["ma_20"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 10),
                instruments=["600519.SH"],
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["rows_written"], 10)
            self.assertEqual(len(results[0]["partitions_written"]), 1)
            self.assertEqual(results[0]["last_materialized_date"], "2024-02-10")

            with RepositorySession(database) as repositories:
                definition = repositories.factor_definition.get("ma_20")

            self.assertIsNotNone(definition)
            assert definition is not None
            self.assertEqual(definition.last_materialized_date, "2024-02-10")

            store = ParquetFactorStore(factor_root)
            frame = store.read_dataset(storage_key="ma/v1/window_20")
            self.assertEqual(frame.height, 41)

    def test_refresh_factors_resumes_from_last_materialized_date_within_month(
        self,
    ) -> None:
        from modules.factors.refresh_factors import refresh_factors
        from modules.factors.storage import ParquetFactorStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            factor_root = root / "research" / "factors"
            SQLiteSchemaManager(database).initialize()
            self._seed_market_data(
                database,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 10),
            )

            refresh_factors(
                database,
                factor_root,
                factor_ids=["ma_20"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 25),
                instruments=["600519.SH"],
            )
            results = refresh_factors(
                database,
                factor_root,
                factor_ids=["ma_20"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 10),
                instruments=["600519.SH"],
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["rows_written"], 16)
            self.assertEqual(len(results[0]["partitions_written"]), 2)
            self.assertEqual(results[0]["last_materialized_date"], "2024-02-10")

            store = ParquetFactorStore(factor_root)
            frame = store.read_dataset(storage_key="ma/v1/window_20")
            self.assertEqual(frame.height, 41)
            january_frame = frame.filter(
                pl.col("trade_date") <= pl.lit(date(2024, 1, 31))
            )
            self.assertEqual(january_frame.height, 31)

    def test_refresh_factors_force_recomputes_requested_range(self) -> None:
        from modules.factors.refresh_factors import refresh_factors
        from modules.factors.storage import ParquetFactorStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            factor_root = root / "research" / "factors"
            SQLiteSchemaManager(database).initialize()
            self._seed_market_data(
                database,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 10),
            )

            refresh_factors(
                database,
                factor_root,
                factor_ids=["ma_20"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 25),
                instruments=["600519.SH"],
            )
            results = refresh_factors(
                database,
                factor_root,
                factor_ids=["ma_20"],
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 10),
                instruments=["600519.SH"],
                force=True,
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["rows_written"], 41)
            self.assertEqual(len(results[0]["partitions_written"]), 2)
            self.assertEqual(results[0]["last_materialized_date"], "2024-02-10")

            store = ParquetFactorStore(factor_root)
            frame = store.read_dataset(storage_key="ma/v1/window_20")
            self.assertEqual(frame.height, 41)

    def test_refresh_factors_persists_monthly_progress_before_later_failure(
        self,
    ) -> None:
        from modules.factors.refresh_factors import refresh_factors
        from modules.factors.storage import ParquetFactorStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            factor_root = root / "research" / "factors"
            SQLiteSchemaManager(database).initialize()
            self._seed_market_data(
                database,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 10),
            )

            original_write_month_partition = ParquetFactorStore.write_month_partition
            call_count = 0

            def fail_on_second_month(self, *, storage_key, frame, year, month):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise RuntimeError("simulated failure")
                return original_write_month_partition(
                    self,
                    storage_key=storage_key,
                    frame=frame,
                    year=year,
                    month=month,
                )

            with patch.object(
                ParquetFactorStore,
                "write_month_partition",
                autospec=True,
                side_effect=fail_on_second_month,
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                    refresh_factors(
                        database,
                        factor_root,
                        factor_ids=["ma_20"],
                        start_date=date(2024, 1, 1),
                        end_date=date(2024, 2, 10),
                        instruments=["600519.SH"],
                    )

            with RepositorySession(database) as repositories:
                definition = repositories.factor_definition.get("ma_20")

            self.assertIsNotNone(definition)
            assert definition is not None
            self.assertEqual(definition.last_materialized_date, "2024-01-31")

    def _seed_market_data(
        self,
        database: SQLiteDatabase,
        *,
        start_date: date = date(2024, 1, 1),
        end_date: date = date(2024, 1, 25),
    ) -> None:
        now = now_shanghai()
        started_at = now.strftime("%Y-%m-%d %H:%M:%S")
        timestamp = format_timestamp(now)

        with RepositorySession(database, transactional=True) as repositories:
            repositories.factor_definition.upsert(
                FactorDefinitionRecord(
                    factor_id="ma_20",
                    version="v1",
                    factor_name="20日均线",
                    category="trend",
                    compute_ref=(
                        "modules.factors.builtin.trend:SimpleMovingAverageFactor"
                    ),
                    params={"window": [20]},
                    output_columns=["ma_20"],
                    storage_key="ma/v1/window_20",
                    description="用于趋势研究的 20 日均线",
                    status="active",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
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
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    request_params={},
                    status="pending",
                    started_at=started_at,
                    created_at=started_at,
                    updated_at=started_at,
                )
            )

            daily_quotes: list[DailyQuoteRecord] = []
            total_days = (end_date - start_date).days + 1
            for offset in range(total_days):
                trade_date = start_date + timedelta(days=offset)
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
