from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

Severity = Literal["warn", "reject"]
BatchStatus = Literal["pending", "running", "success", "failed"]


class IngestionBatchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    batch_key: str | None = None
    source_name: str
    resource_type: str
    sync_mode: str
    start_date: str | None = None
    end_date: str | None = None
    request_params: dict[str, Any]
    status: BatchStatus
    started_at: str
    finished_at: str | None = None
    raw_count: int = 0
    valid_count: int = 0
    loaded_count: int = 0
    rejected_count: int = 0
    retry_count: int = 0
    error_summary: str | None = None
    created_at: str
    updated_at: str


class DataQualityIssueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    ingestion_batch_id: int
    resource_type: str
    severity: Severity
    issue_code: str
    business_key: str
    message: str
    raw_payload: dict[str, Any] | None = None
    created_at: str


class StockRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    market: str
    exchange: str
    symbol: str
    ticker: str | None = None
    name: str
    asset_type: str
    currency: str
    lot_size: int
    listed_at: date | None = None
    delisted_at: date | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> "StockRecord":
        if self.delisted_at and self.listed_at and self.listed_at > self.delisted_at:
            raise ValueError("listed_at must be <= delisted_at")
        return self


class TradingCalendarRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    market: str
    trade_date: date
    is_open: bool
    created_at: datetime
    updated_at: datetime


class DailyQuoteRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    stock_id: int
    trade_date: date
    open: int
    high: int
    low: int
    close: int
    volume: int
    turnover: int | None = None
    ingestion_batch_id: int
    ingested_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_ohlc(self) -> "DailyQuoteRecord":
        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError("OHLC must be positive")
        if self.high < self.open or self.high < self.close or self.high < self.low:
            raise ValueError("high price is invalid")
        if self.low > self.open or self.low > self.close:
            raise ValueError("low price is invalid")
        if self.volume < 0:
            raise ValueError("volume must be >= 0")
        if self.turnover is not None and self.turnover < 0:
            raise ValueError("turnover must be >= 0")
        return self


class RawManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion_batch_id: int
    batch_key: str
    source_name: str
    resource_type: str
    sync_mode: str
    request_params: dict[str, Any]
    started_at: str
    finished_at: str | None = None
    row_count_raw: int = 0
    status: str
    records_path: str | None = None
    records_sha256: str | None = None
