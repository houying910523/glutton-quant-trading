from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import polars as pl
    from modules.datasource.service.stock_daily_service import StockDailyService
except ModuleNotFoundError:  # pragma: no cover - optional at test runtime
    pl = None
    StockDailyService = None


@unittest.skipIf(StockDailyService is None, "polars is not installed")
class StockDailyServiceNormalizeColumnsTest(unittest.TestCase):
    def test_normalize_columns_returns_defaults_when_columns_missing(self) -> None:
        columns = StockDailyService._normalize_columns(None)

        self.assertEqual(
            columns,
            ["open", "high", "low", "close", "volume", "turnover"],
        )

    def test_normalize_columns_deduplicates_requested_columns(self) -> None:
        columns = StockDailyService._normalize_columns(["close", "volume", "close"])

        self.assertEqual(columns, ["close", "volume"])

    def test_normalize_columns_rejects_unknown_column(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported daily bar column"):
            StockDailyService._normalize_columns(["pe_ratio"])


@unittest.skipIf(pl is None, "polars is not installed")
class StockDailyServiceEmptyFrameTest(unittest.TestCase):
    def test_empty_frame_uses_expected_schema(self) -> None:
        frame = StockDailyService._empty_frame(["close", "volume", "turnover"])

        self.assertEqual(
            frame.schema,
            {
                "trade_date": pl.Date,
                "instrument_id": pl.Utf8,
                "close": pl.Float64,
                "volume": pl.Int64,
                "turnover": pl.Float64,
            },
        )
        self.assertEqual(frame.height, 0)


class ResolveDatasetRootTest(unittest.TestCase):
    def test_resolve_dataset_root_joins_indicator_root_and_storage_key(self) -> None:
        from modules.indicators.storage.path_resolver import resolve_dataset_root

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            indicator_root = root / "factors"
            storage_key = "ma/v1/window_20"

            dataset_root = resolve_dataset_root(indicator_root, storage_key)

            self.assertEqual(dataset_root, indicator_root / "ma" / "v1" / "window_20")


class ResolvePartitionPathTest(unittest.TestCase):
    def test_resolve_partition_path_builds_year_partition_path(self) -> None:
        from modules.indicators.storage.path_resolver import resolve_partition_path

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            indicator_root = root / "factors"
            storage_key = "ma/v1/window_20"

            partition_path = resolve_partition_path(
                indicator_root,
                storage_key,
                year=2024,
            )

            self.assertEqual(
                partition_path,
                indicator_root
                / "ma"
                / "v1"
                / "window_20"
                / "year=2024"
                / "data.parquet",
            )


@unittest.skipIf(pl is None, "polars is not installed")
class IndicatorStoreWriteYearPartitionTest(unittest.TestCase):
    def test_write_year_partition_persists_string_trade_date_and_reads_back_as_date(
        self,
    ) -> None:
        from datetime import date

        from modules.indicators.storage.indicator_store import IndicatorStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            indicator_root = root / "factors"
            store = IndicatorStore(indicator_root)
            storage_key = "ma/v1/window_20"

            frame = pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "instrument_id": ["600519.SH", "600519.SH"],
                    "ma_20": [10.1, 10.2],
                }
            )
            written = store.write_year_partition(
                storage_key=storage_key,
                frame=frame,
                year=2024,
            )
            expected_path = store.partition_path(storage_key, year=2024)

            self.assertEqual(written, expected_path)
            self.assertTrue(written.exists())
            self.assertTrue(store.exists(storage_key=storage_key))

            raw_loaded = pl.read_parquet(written)
            self.assertIn(
                raw_loaded.schema["trade_date"],
                {pl.Utf8, getattr(pl, "String", pl.Utf8)},
            )
            self.assertEqual(
                raw_loaded["trade_date"].to_list(), ["2024-01-02", "2024-01-03"]
            )

            loaded = store.read_year_partition(storage_key=storage_key, year=2024)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.schema["trade_date"], pl.Date)
            self.assertEqual(
                loaded["trade_date"].to_list(), [date(2024, 1, 2), date(2024, 1, 3)]
            )
            self.assertEqual(loaded["ma_20"].to_list(), [10.1, 10.2])


if __name__ == "__main__":
    unittest.main()
