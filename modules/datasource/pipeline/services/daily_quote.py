from __future__ import annotations

from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Generator


from modules.datasource.adaptors import AdapterType
from modules.repositories import RepositorySession
from modules.repositories.models import (
    DailyQuoteRecord,
    IngestionBatchRecord,
)
from modules.datasource.pipeline.services.base import BasePipeline, PipelineOutcome
from modules.datasource.adaptors.base import StockDailyQuoteFetcher


@dataclass
class Task:
    stock_id: int
    symbol: str
    start_date: str  # yyyyMMdd
    end_date: str  # yyyyMMdd


class DailyQuotePipeline(BasePipeline):
    resource_type = "daily_quote"

    def _process(
        self,
        repositories: RepositorySession,
        batch: IngestionBatchRecord,
        adaptor_type: AdapterType,
        **kwargs: Any,
    ) -> PipelineOutcome:
        from modules.datasource.adaptors.base import create_stock_daily_quote_fetcher

        stock_daily_quote_fetcher = create_stock_daily_quote_fetcher(adaptor_type)
        active_stocks = self.active_stock_symbols()
        symbol_to_id_mapping = {tp[1]: tp[0] for tp in active_stocks}
        symbols = kwargs.get("symbols") or list(symbol_to_id_mapping.keys())
        start_date = self.required("start_date", kwargs)
        end_date = self.required("end_date", kwargs)
        refresh = kwargs.get("refresh", False)

        try:
            if refresh:
                # 全量数据刷新
                tasks = self._refresh_all_daily_quote(
                    symbols, start_date, end_date, symbol_to_id_mapping
                )
            else:
                # 增量补充
                tasks = self._incremental_daily_quote(
                    symbols, start_date, end_date, symbol_to_id_mapping
                )

            total = 0
            for daily_quote_list in self._parallel_process_daily_quote(
                stock_daily_quote_fetcher, tasks, batch
            ):
                repositories.daily_quote.upsert_many(daily_quote_list)
                total += len(daily_quote_list)

            return PipelineOutcome(
                status="success",
                raw_count=total,
                loaded_count=total,
                valid_count=total,
                rejected_count=0,
            )
        except Exception as e:
            raise e

    def _refresh_all_daily_quote(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        symbol_to_id_mapping: dict[str, int],
    ) -> list[Task]:
        tasks = [
            Task(
                stock_id=symbol_to_id_mapping[symbol],
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            for symbol in symbols
        ]
        return tasks

    def _incremental_daily_quote(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        symbol_to_id_mapping: dict[str, int],
    ) -> list[Task]:
        pass

    @classmethod
    def _parallel_process_daily_quote(
        cls,
        stock_daily_quote_fetcher: StockDailyQuoteFetcher,
        tasks: list[Task],
        batch: IngestionBatchRecord,
    ) -> Generator[list[DailyQuoteRecord], None, None]:

        from queue import Queue

        queue = Queue(maxsize=len(tasks))

        def fetch_and_write(task: Task) -> None:
            records = stock_daily_quote_fetcher.fetch(
                task.symbol,
                task.start_date,
                task.end_date,
                batch_id=batch.id,
                stock_id=task.stock_id,
            )
            queue.put(records, block=True)

        def async_submit_task() -> None:
            with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
                future_list = []
                for task in tasks:
                    future = executor.submit(fetch_and_write, task)
                    future_list.append(future)

                for future in as_completed(future_list):
                    future.result()
            queue.put("done")

        import threading

        threading.Thread(target=async_submit_task).start()

        while True:
            obj = queue.get()
            if isinstance(obj, str) and obj == "done":
                break
            yield obj

    @classmethod
    def required(cls, key: str, kwargs: dict[str, Any]) -> Any:
        if key not in kwargs or kwargs.get(key) is None:
            raise Exception()
        return kwargs[key]

    def active_stock_symbols(self) -> list[tuple[int, str]]:
        with RepositorySession(self._database) as repositories:
            return repositories.stock.list_active_symbols()

    def _upsert_records(
        self,
        repositories: RepositorySession,
        records: list[DailyQuoteRecord],
    ) -> None:
        repositories.daily_quote.upsert_many(records)
