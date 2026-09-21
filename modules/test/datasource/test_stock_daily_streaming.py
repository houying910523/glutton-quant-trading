from __future__ import annotations

import unittest
from unittest.mock import patch

from modules.datasource.pipeline.stock_daily import StockDailyPipeline, Task
from modules.utils.time_util import now_shanghai, parse_date
from modules.repositories.models import StockDailyRecord, IngestionBatchRecord


class FakeDailyQuoteFetcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, int, int]] = []

    def fetch(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        stock_id: int,
        batch_id: int,
    ) -> list[StockDailyRecord]:
        self.calls.append((symbol, start_date, end_date, stock_id, batch_id))
        now = now_shanghai()
        return [
            StockDailyRecord(
                id=None,
                stock_id=stock_id,
                trade_date=parse_date(start_date),
                open=1000,
                high=1010,
                low=990,
                close=1005,
                volume=100000,
                amount=100000000,
                turnover=100000000,
                ingestion_batch_id=batch_id,
                ingested_at=now,
                updated_at=now,
            )
        ]


class FakeProgressBar:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.updates = 0
        self.closed = False

    def update(self, count: int = 1) -> None:
        self.updates += count

    def close(self) -> None:
        self.closed = True


class ParallelProcessDailyQuoteTest(unittest.TestCase):
    @patch("tqdm.tqdm")
    @patch("modules.datasource.adaptors.base.create_stock_daily_quote_fetcher")
    def test_parallel_process_daily_quote_yields_record_batches_for_each_task(
        self,
        mock_create_stock_daily_quote_fetcher,
        mock_tqdm,
    ) -> None:
        batch = IngestionBatchRecord(
            id=42,
            batch_key="daily_quote_2026-09-05_001",
            source_name="akshare",
            resource_type="stock_daily",
            sync_mode="incremental",
            start_date=None,
            end_date=None,
            request_params={},
            status="running",
            started_at="2026-09-05 10:00:00",
            finished_at=None,
            raw_count=0,
            valid_count=0,
            loaded_count=0,
            rejected_count=0,
            retry_count=0,
            error_summary=None,
            created_at="2026-09-05 10:00:00",
            updated_at="2026-09-05 10:00:00",
        )
        tasks = [
            Task(
                stock_id=1,
                symbol="600519",
                history_start_date="2024-08-26",
                start_date="2024-08-26",
                end_date="2024-08-26",
            ),
            Task(
                stock_id=2,
                symbol="000001",
                history_start_date="2024-08-26",
                start_date="2024-08-26",
                end_date="2024-08-26",
            ),
        ]
        fetcher = FakeDailyQuoteFetcher()
        progress_bars: list[FakeProgressBar] = []

        def create_progress_bar(*args, **kwargs) -> FakeProgressBar:
            progress_bar = FakeProgressBar(*args, **kwargs)
            progress_bars.append(progress_bar)
            return progress_bar

        mock_create_stock_daily_quote_fetcher.return_value = fetcher
        mock_tqdm.side_effect = create_progress_bar

        yielded = list(
            StockDailyPipeline._parallel_process_daily_quote(
                "akshare",
                tasks,
                batch,
            )
        )

        self.assertEqual(len(yielded), 2)
        self.assertEqual(
            sorted(task.symbol for task, _ in yielded), ["000001", "600519"]
        )
        self.assertEqual([len(records) for _, records in yielded], [1, 1])
        self.assertEqual(
            sorted(fetcher.calls),
            [
                ("000001", "2024-08-26", "2024-08-26", 2, 42),
                ("600519", "2024-08-26", "2024-08-26", 1, 42),
            ],
        )
        self.assertEqual(len(progress_bars), 1)
        self.assertEqual(progress_bars[0].kwargs["total"], 2)
        self.assertEqual(progress_bars[0].updates, 2)
        self.assertTrue(progress_bars[0].closed)


if __name__ == "__main__":
    unittest.main()
