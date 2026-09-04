from __future__ import annotations

from pathlib import Path

from modules.config import DEFAULT_DB_PATH, DEFAULT_RAW_ROOT, PROJECT_ROOT
from modules.repositories.database import SQLiteDatabase
from modules.repositories.schema import SQLiteSchemaManager
from modules.datasource.pipeline.raw_store import RawStore
from modules.datasource.shared import (
    format_timestamp,
    parse_date,
)
from modules.repositories import RepositorySession


class JobRuntime:
    def __init__(self):
        self._database = SQLiteDatabase(_resolve_project_path(DEFAULT_DB_PATH))
        self._raw_store = RawStore(_resolve_project_path(DEFAULT_RAW_ROOT))
        self._schema_manager = SQLiteSchemaManager(self._database)
        self._schema_manager.initialize()

    @property
    def database(self) -> SQLiteDatabase:
        return self._database

    @property
    def raw_store(self) -> RawStore:
        return self._raw_store

    def fail_batch(self, *, batch_id: int, error_summary: str) -> None:
        finished_at = format_timestamp()
        with RepositorySession(self.database, transactional=True) as repositories:
            repositories.batch.complete_batch(
                batch_id=batch_id,
                status="failed",
                finished_at=finished_at,
                row_count_raw=0,
                row_count_valid=0,
                row_count_loaded=0,
                row_count_rejected=0,
                error_summary=error_summary,
            )

    def pending_daily_quote_dates(self, *, start_date: str, end_date: str) -> list[str]:
        with RepositorySession(self.database) as repositories:
            open_dates = repositories.trading_calendar.list_open_trade_dates(
                start_date=start_date,
                end_date=end_date,
            )
            loaded_dates = repositories.daily_quote.list_loaded_trade_dates(
                start_date=start_date,
                end_date=end_date,
            )
            latest_batches = repositories.batch.list_latest_daily_quote_batches(
                start_date,
                end_date,
            )
            warning_batch_ids = repositories.quality_issue.list_issue_batch_ids(
                issue_code="daily_quote_coverage_below_threshold",
                ingestion_batch_ids=[row["id"] for row in latest_batches.values()],
            )
        pending_dates: list[str] = []
        for trade_date in open_dates:
            latest_batch = latest_batches.get(trade_date)
            if trade_date not in loaded_dates:
                pending_dates.append(trade_date)
                continue
            if latest_batch is None:
                pending_dates.append(trade_date)
                continue
            if latest_batch["status"] == "failed":
                pending_dates.append(trade_date)
                continue
            if latest_batch["id"] in warning_batch_ids:
                pending_dates.append(trade_date)
        return pending_dates


def resolve_calendar_range(
    start_date: str | None, end_date: str | None
) -> tuple[str, str]:
    if not start_date or not end_date:
        runtime = JobRuntime.build()
        return runtime.default_calendar_range()
    return parse_date(start_date).isoformat(), parse_date(end_date).isoformat()


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
