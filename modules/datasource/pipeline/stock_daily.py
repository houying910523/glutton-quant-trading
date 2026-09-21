from __future__ import annotations

from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Generator

from modules.datasource.adaptors import AdapterType
from modules.datasource.pipeline.base import BasePipeline, PipelineOutcome
from modules.repositories import RepositorySession
from modules.repositories.models import StockDailyRecord, IngestionBatchRecord
from modules.utils.time_util import now_shanghai, parse_date

DEFAULT_HISTORY_START_DATE = "1991-01-01"


@dataclass(frozen=True)
class StockSyncTarget:
    stock_id: int
    symbol: str
    listed_at: str | None = None
    force: bool | None = None


@dataclass
class Task:
    stock_id: int
    symbol: str
    history_start_date: str
    start_date: str
    end_date: str


class StockDailyPipeline(BasePipeline):
    resource_type = "stock_daily"

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
        for task, records in self._parallel_process_daily_quote(
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

    @classmethod
    def _incremental_daily_quote(
        cls,
        repositories: RepositorySession,
        target_stocks: list[StockSyncTarget],
    ) -> list[Task]:
        today = now_shanghai().date().isoformat()
        tasks: list[Task] = []
        for stock in target_stocks:
            history_start_date = stock.listed_at or DEFAULT_HISTORY_START_DATE
            latest_trade_date = repositories.stock_daily.get_latest_trade_date(
                stock_id=stock.stock_id
            )
            if latest_trade_date and not stock.force:
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
    def _parallel_process_daily_quote(
        cls,
        adaptor_type: AdapterType,
        tasks: list[Task],
        batch: IngestionBatchRecord,
    ) -> Generator[tuple[Task, list[StockDailyRecord]], None, None]:
        if not tasks:
            return

        from queue import Queue

        sentinel = object()
        queue = Queue(maxsize=len(tasks) + 1)

        from modules.datasource.adaptors.base import create_stock_daily_quote_fetcher
        from tqdm import tqdm

        def fetch_and_write(task: Task) -> None:
            stock_daily_quote_fetcher = create_stock_daily_quote_fetcher(adaptor_type)
            records = stock_daily_quote_fetcher.fetch(
                task.symbol,
                task.start_date,
                task.end_date,
                batch_id=batch.id,
                stock_id=task.stock_id,
            )
            queue.put((task, records), block=True)

        def async_submit_task() -> None:
            try:
                with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
                    future_list = []
                    for task in tasks:
                        future = executor.submit(fetch_and_write, task)
                        future_list.append(future)

                    for future in as_completed(future_list):
                        future.result()
            except Exception as exc:
                queue.put(exc, block=True)
            finally:
                queue.put(sentinel, block=True)

        import threading

        threading.Thread(target=async_submit_task).start()

        progress = tqdm(
            total=len(tasks),
            ncols=100,
            desc="Fetching",
            leave=False,
            unit="stock",
        )
        try:
            while True:
                obj = queue.get()
                if obj is sentinel:
                    break
                if isinstance(obj, Exception):
                    raise obj
                progress.update(1)
                yield obj
        finally:
            progress.close()

    @classmethod
    def _upsert_records(
        cls,
        repositories: RepositorySession,
        records: list[StockDailyRecord],
    ) -> None:
        repositories.stock_daily.upsert_many(records)
        repositories.commit()

    @classmethod
    def _select_target_stocks(
        cls,
        repositories: RepositorySession,
        kwargs: dict[str, Any],
    ) -> list[StockSyncTarget]:
        stock_ids = set(cls._normalize_int_filters(kwargs, "stock_id", "stock_ids"))
        symbols = set(cls._normalize_str_filters(kwargs, "symbol"))
        force = kwargs.get("force", False)

        targets = [
            StockSyncTarget(
                stock_id=stock_id,
                symbol=symbol,
                listed_at=listed_at,
                force=force,
            )
            for stock_id, symbol, listed_at in repositories.stock_info.list_active_sync_targets(
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
