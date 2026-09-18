from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.datasource.pipeline.raw_store import RawStore
from modules.datasource.pipeline.stock import StockPipeline
from modules.datasource.exceptions import PipelineExecutionError
from modules.utils.time_util import now_shanghai
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import StockRecord
from modules.repositories.schema import SQLiteSchemaManager


class FakeStockFetcher:
    def fetch(self) -> list[StockRecord]:
        now = now_shanghai()
        return [
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
            )
        ]


class FailingStockFetcher:
    def fetch(self) -> list[StockRecord]:
        raise RuntimeError("boom")


class StockPipelineCommitTest(unittest.TestCase):
    def test_run_commits_upserted_stocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            SQLiteSchemaManager(database).initialize()
            pipeline = StockPipeline(database, RawStore(root / "raw"))

            with patch(
                "modules.datasource.adaptors.base.create_stock_fetcher",
                return_value=FakeStockFetcher(),
            ):
                result = pipeline.run("akshare", sync_mode="full")

            self.assertEqual(result.status, "success")
            self.assertEqual(result.loaded_count, 1)
            with RepositorySession(database) as repositories:
                rows = repositories.stock.load_existing_by_natural_keys(
                    [("CN", "SSE", "600519")]
                )
            self.assertIn(("CN", "SSE", "600519"), rows)

    def test_run_preserves_original_error_when_fetch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            SQLiteSchemaManager(database).initialize()
            pipeline = StockPipeline(database, RawStore(root / "raw"))

            with patch(
                "modules.datasource.adaptors.base.create_stock_fetcher",
                return_value=FailingStockFetcher(),
            ):
                with self.assertRaisesRegex(PipelineExecutionError, "boom"):
                    pipeline.run("akshare", sync_mode="full")


if __name__ == "__main__":
    unittest.main()
