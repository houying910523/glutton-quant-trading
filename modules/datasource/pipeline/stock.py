from __future__ import annotations

from typing import Any

from modules.datasource.adaptors import AdapterType
from modules.repositories import RepositorySession
from modules.repositories.models import IngestionBatchRecord, StockRecord
from .base import BasePipeline, PipelineOutcome


class StockPipeline(BasePipeline):
    resource_type = "stock"

    def _process(
        self,
        repositories: RepositorySession,
        batch: IngestionBatchRecord,
        adaptor_type: AdapterType,
        **kwargs: Any,
    ) -> PipelineOutcome:
        from modules.datasource.adaptors.base import create_stock_fetcher

        stock_fetcher = create_stock_fetcher(adaptor_type)
        rows = stock_fetcher.fetch()
        existing_rows = repositories.stock.load_existing_by_natural_keys(
            [
                ("CN", row.exchange, row.symbol)
                for row in rows
                if row.exchange in {"SSE", "SZSE"} and row.symbol
            ]
        )

        accepted: list[StockRecord] = []
        rejected: list[StockRecord] = []
        seen_business_keys: set[tuple[str, str, str]] = set()
        for row in rows:
            business_key = ("CN", row.exchange, row.symbol)
            existing_row = existing_rows.get(business_key)
            if existing_row is None or existing_row["name"] != row.name:
                accepted.append(row)
                seen_business_keys.add(business_key)
                continue
            rejected.append(row)

        repositories.stock.upsert_many(accepted)

        return PipelineOutcome(
            status="success",
            raw_count=len(rows),
            loaded_count=len(accepted),
            valid_count=len(accepted),
            rejected_count=len(rejected),
            rejected_records=rejected,
        )
