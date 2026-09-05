from __future__ import annotations

import sys
from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Generator

from modules.datasource.adaptors import AdapterType
from modules.datasource.pipeline.services.base import BasePipeline, PipelineOutcome
from modules.datasource.shared import now_shanghai, parse_date
from modules.repositories import RepositorySession
from modules.repositories.models import DailyQuoteRecord, IngestionBatchRecord

DEFAULT_HISTORY_START_DATE = "1991-01-01"


@dataclass(frozen=True)
class StockSyncTarget:
    stock_id: int
    symbol: str
    listed_at: str | None


@dataclass
class Task:
    stock_id: int
    symbol: str
    history_start_date: str
    start_date: str
    end_date: str


class DailyQuotePipeline(BasePipeline):
    resource_type = "daily_quote"

    def create_running_batch(self, *, source_name: str, **kwargs):
        kwargs.setdefault("sync_mode", "incremental")
        return super().create_running_batch(source_name=source_name, **kwargs)

    def _process(
        self,
        repositories: RepositorySession,
        batch: IngestionBatchRecord,
        adaptor_type: AdapterType,
        **kwargs: Any,
    ) -> PipelineOutcome:
        target_stocks = self._select_target_stocks(repositories, kwargs)
        tasks = self._incremental_daily_quote(repositories, target_stocks)

        total = 0
        for task, records in self._sequence_process_daily_quote(
            adaptor_type, tasks, batch
        ):
            self._upsert_records(repositories, records)
            total += len(records)

        return PipelineOutcome(
            status="success",
            raw_count=total,
            loaded_count=total,
            valid_count=total,
            rejected_count=0,
        )

    def _incremental_daily_quote(
        self,
        repositories: RepositorySession,
        target_stocks: list[StockSyncTarget],
    ) -> list[Task]:
        today = now_shanghai().date().isoformat()
        tasks: list[Task] = []
        for stock in target_stocks:
            history_start_date = stock.listed_at or DEFAULT_HISTORY_START_DATE
            latest_trade_date = repositories.daily_quote.get_latest_trade_date(
                stock_id=stock.stock_id
            )
            if latest_trade_date:
                next_date = parse_date(latest_trade_date)
                if next_date is None:
                    raise ValueError(
                        f"invalid latest trade date for {stock.symbol}: {latest_trade_date}"
                    )
                start_date = (next_date + timedelta(days=1)).isoformat()
            else:
                start_date = history_start_date

            expected_open_dates = repositories.trading_calendar.list_open_trade_dates(
                start_date=start_date,
                end_date=today,
            )
            if not expected_open_dates:
                continue

            tasks.append(
                Task(
                    stock_id=stock.stock_id,
                    symbol=stock.symbol,
                    history_start_date=history_start_date,
                    start_date=start_date,
                    end_date=expected_open_dates[-1],
                )
            )
        return tasks

    @classmethod
    def _sequence_process_daily_quote(
        cls,
        adaptor_type: AdapterType,
        tasks: list[Task],
        batch: IngestionBatchRecord,
    ):
        from modules.datasource.adaptors.base import create_stock_daily_quote_fetcher

        stock_daily_quote_fetcher = create_stock_daily_quote_fetcher(adaptor_type)

        from tqdm import tqdm

        for task in tqdm(
            tasks,
            ncols=100,
            desc="Fetching",
            total=len(tasks),
            leave=False,
            unit="stock",
        ):
            records = stock_daily_quote_fetcher.fetch(
                task.symbol,
                task.start_date,
                task.end_date,
                batch_id=batch.id,
                stock_id=task.stock_id,
            )
            yield task, records

    @classmethod
    def _parallel_process_daily_quote(
        cls,
        adaptor_type: AdapterType,
        tasks: list[Task],
        batch: IngestionBatchRecord,
    ) -> Generator[tuple[Task, list[DailyQuoteRecord]], None, None]:
        if not tasks:
            return

        from queue import Queue

        sentinel = object()
        queue = Queue(maxsize=len(tasks) + 1)

        from modules.datasource.adaptors.base import create_stock_daily_quote_fetcher

        def fetch_and_write(task: Task) -> None:
            sys.stderr.write(f"task {task.stock_id} {task.symbol} start\n")
            stock_daily_quote_fetcher = create_stock_daily_quote_fetcher(adaptor_type)
            records = stock_daily_quote_fetcher.fetch(
                task.symbol,
                task.start_date,
                task.end_date,
                batch_id=batch.id,
                stock_id=task.stock_id,
            )
            sys.stderr.write(f"task {task.stock_id} {task.symbol} fetched\n")
            queue.put((task, records), block=True)

        def async_submit_task() -> None:
            try:
                with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
                    future_list = []
                    for task in tasks:
                        future = executor.submit(fetch_and_write, task)
                        future_list.append(future)

                    sys.stderr.write("waiting for all task done...\n")
                    for future in as_completed(future_list):
                        future.result()
            except Exception as exc:
                queue.put(exc, block=True)
            finally:
                queue.put(sentinel, block=True)
                sys.stderr.write("all task done.\n")

        import threading

        threading.Thread(target=async_submit_task).start()

        while True:
            obj = queue.get()
            if obj is sentinel:
                break
            if isinstance(obj, Exception):
                raise obj
            sys.stderr.write(f"get records {len(obj[1])}")
            yield obj

    def _upsert_records(
        self,
        repositories: RepositorySession,
        records: list[DailyQuoteRecord],
    ) -> None:
        repositories.daily_quote.upsert_many(records)
        repositories.commit()

    def _select_target_stocks(
        self,
        repositories: RepositorySession,
        kwargs: dict[str, Any],
    ) -> list[StockSyncTarget]:
        stock_ids = set(self._normalize_int_filters(kwargs, "stock_id", "stock_ids"))
        symbols = set(self._normalize_str_filters(kwargs, "symbol"))
        targets = [
            StockSyncTarget(
                stock_id=stock_id,
                symbol=symbol,
                listed_at=listed_at,
            )
            for stock_id, symbol, listed_at in repositories.stock.list_active_sync_targets(
                stock_ids=sorted(stock_ids) or None,
                symbols=sorted(symbols) or None,
            )
        ]
        if not targets:
            raise ValueError("no active stock matched the given stock_id/symbol filter")
        return targets

    @classmethod
    def _normalize_str_filters(
        cls,
        kwargs: dict[str, Any],
        *keys: str,
    ) -> list[str]:
        values: list[str] = []
        for key in keys:
            values.extend(cls._coerce_str_values(kwargs.get(key)))
        return values

    @classmethod
    def _normalize_int_filters(
        cls,
        kwargs: dict[str, Any],
        *keys: str,
    ) -> list[int]:
        values: list[int] = []
        for key in keys:
            values.extend(cls._coerce_int_values(kwargs.get(key)))
        return values

    @classmethod
    def _coerce_str_values(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            values: list[str] = []
            for item in value:
                values.extend(cls._coerce_str_values(item))
            return values
        return [str(value).strip()]

    @classmethod
    def _coerce_int_values(cls, value: Any) -> list[int]:
        if value is None:
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            values: list[int] = []
            for item in value:
                values.extend(cls._coerce_int_values(item))
            return values
        raise ValueError(f"unsupported stock id filter type: {type(value).__name__}")
