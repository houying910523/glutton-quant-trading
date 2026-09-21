from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from modules.datasource.exceptions import PipelineExecutionError
from modules.datasource.pipeline.stock_info import StockInfoPipeline
from modules.repositories.models import IngestionBatchRecord, StockInfoRecord
from modules.utils.time_util import now_shanghai


class FakeStockFetcher:
    def fetch(self) -> list[StockInfoRecord]:
        now = now_shanghai()
        return [
            StockInfoRecord(
                id=None,
                market="CN",
                exchange="SSE",
                symbol="600519",
                ticker="600519",
                name="贵州茅台",
                listed_at=None,
                delisted_at=None,
                status="active",
                created_at=now,
                updated_at=now,
            )
        ]


class FailingStockFetcher:
    def fetch(self) -> list[StockInfoRecord]:
        raise RuntimeError("boom")


class StockPipelineRunTest(unittest.TestCase):
    @patch("modules.datasource.adaptors.base.create_stock_fetcher")
    @patch("modules.datasource.pipeline.base.RepositorySession")
    @patch.object(StockInfoPipeline, "create_running_batch")
    def test_run_commits_upserted_stocks(
        self,
        mock_create_running_batch,
        mock_repository_session,
        mock_create_stock_fetcher,
    ) -> None:
        pipeline = StockInfoPipeline(MagicMock())
        batch = self._make_batch(status="running")
        process_session = MagicMock()
        process_session.__enter__.return_value = process_session
        process_session.__exit__.return_value = None
        process_session.stock_info.load_existing_by_natural_keys.return_value = {}

        mock_create_running_batch.return_value = batch
        mock_repository_session.return_value = process_session
        mock_create_stock_fetcher.return_value = FakeStockFetcher()

        result = pipeline.run("akshare", sync_mode="full")

        process_session.stock_info.load_existing_by_natural_keys.assert_called_once_with(
            [("CN", "SSE", "600519")]
        )
        process_session.stock_info.upsert_many.assert_called_once()
        persisted_rows = process_session.stock_info.upsert_many.call_args.args[0]
        self.assertEqual([row.symbol for row in persisted_rows], ["600519"])
        process_session.batch.complete_batch.assert_called_once()
        self.assertEqual(result.status, "success")
        self.assertEqual(result.loaded_count, 1)

    @patch("modules.datasource.adaptors.base.create_stock_fetcher")
    @patch("modules.datasource.pipeline.base.RepositorySession")
    @patch.object(StockInfoPipeline, "create_running_batch")
    def test_run_preserves_original_error_when_fetch_fails(
        self,
        mock_create_running_batch,
        mock_repository_session,
        mock_create_stock_fetcher,
    ) -> None:
        pipeline = StockInfoPipeline(MagicMock())
        batch = self._make_batch(status="running")
        process_session = MagicMock()
        process_session.__enter__.return_value = process_session
        process_session.__exit__.return_value = None
        failure_session = MagicMock()
        failure_session.__enter__.return_value = failure_session
        failure_session.__exit__.return_value = None

        mock_create_running_batch.return_value = batch
        mock_repository_session.side_effect = [process_session, failure_session]
        mock_create_stock_fetcher.return_value = FailingStockFetcher()

        with self.assertRaisesRegex(PipelineExecutionError, "boom"):
            pipeline.run("akshare", sync_mode="full")

        failure_session.batch.complete_batch.assert_called_once()
        self.assertEqual(
            failure_session.batch.complete_batch.call_args.kwargs["error_summary"],
            "boom",
        )

    @classmethod
    def _make_batch(cls, *, status: str) -> IngestionBatchRecord:
        return IngestionBatchRecord(
            id=1,
            batch_key="stock_info_2026-09-20_0001",
            source_name="akshare",
            resource_type="stock_info",
            sync_mode="full",
            start_date=None,
            end_date=None,
            request_params={},
            status=status,
            started_at="2026-09-20 10:00:00",
            finished_at=None,
            raw_count=0,
            valid_count=0,
            loaded_count=0,
            rejected_count=0,
            retry_count=0,
            error_summary=None,
            created_at="2026-09-20 10:00:00",
            updated_at="2026-09-20 10:00:00",
        )


if __name__ == "__main__":
    unittest.main()
