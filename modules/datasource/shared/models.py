from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ResourceType = Literal["stock", "trading_calendar", "daily_quote"]
SyncMode = Literal["full", "incremental", "refresh"]


@dataclass(frozen=True)
class FetchRequest:
    resource_type: ResourceType
    sync_mode: SyncMode
    start_date: str | None = None
    end_date: str | None = None
    symbols: list[str] | None = None
    trade_date: str | None = None


@dataclass(frozen=True)
class RawRecord:
    ingestion_batch_id: int
    source_name: str
    resource_type: ResourceType
    source_record_key: str
    fetched_at: str
    payload: dict[str, Any]
