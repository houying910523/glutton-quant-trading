from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any


from modules.datasource.adaptors import AdapterType
from modules.datasource.shared import now_shanghai, parse_date
from modules.repositories import RepositorySession
from modules.repositories.models import IngestionBatchRecord, TradingCalendarRecord

from .base import BasePipeline, PipelineOutcome

if TYPE_CHECKING:
    pass


class TradingCalendarPipeline(BasePipeline):
    resource_type = "trading_calendar"

    def _process(
        self,
        repositories: RepositorySession,
        batch: IngestionBatchRecord,
        adaptor_type: AdapterType,
        **kwargs: Any,
    ) -> PipelineOutcome:
        if not batch.start_date or not batch.end_date:
            raise ValueError("akshare calendar batch requires start and end date")

        from modules.datasource.adaptors.base import create_trading_calendar_fetcher

        trading_calendar_fetcher = create_trading_calendar_fetcher(adaptor_type)

        now = now_shanghai()
        accepted_map: dict[str, TradingCalendarRecord] = {}
        records = trading_calendar_fetcher.fetch(**kwargs)
        open_dates: set[str] = set(records)
        current = parse_date(batch.start_date)
        end_date = parse_date(batch.end_date)
        while current and end_date and current <= end_date:
            trade_date_text = current.isoformat()
            accepted_map[trade_date_text] = TradingCalendarRecord(
                id=None,
                market="CN",
                trade_date=current,
                is_open=trade_date_text in open_dates,
                created_at=now,
                updated_at=now,
            )
            current += timedelta(days=1)

        accepted = list(accepted_map.values())

        repositories.trading_calendar.upsert_many(accepted)

        return PipelineOutcome(
            status="success",
            raw_count=len(records),
            loaded_count=len(accepted),
            valid_count=len(accepted),
            rejected_count=0,
        )
