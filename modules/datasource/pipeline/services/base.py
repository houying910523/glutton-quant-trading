from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

from modules.datasource.adaptors import AdapterType
from modules.datasource.pipeline.raw_store import RawStore
from modules.datasource.shared import PipelineExecutionError, format_timestamp
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import IngestionBatchRecord, BatchStatus


@dataclass
class PipelineOutcome:
    status: BatchStatus
    raw_count: int = 0
    loaded_count: int = 0
    valid_count: int = 0
    rejected_count: int = 0
    rejected_records: list[Any] | None = None
    error_summary: str | None = None


T = TypeVar("T")


class BasePipeline:
    resource_type: str

    def __init__(self, database: SQLiteDatabase, raw_store: RawStore) -> None:
        self._database = database
        self._raw_store = raw_store

    def create_running_batch(self, *, source_name: str, **kwargs):
        with RepositorySession(self._database, transactional=True) as repositories:
            now = format_timestamp()
            batch = repositories.batch.create_batch(
                record=IngestionBatchRecord(
                    source_name=source_name,
                    resource_type=self.resource_type,
                    sync_mode=kwargs.get("sync_mode", "full"),
                    start_date=kwargs.get("start_date"),
                    end_date=kwargs.get("end_date"),
                    request_params={},
                    status="pending",
                    started_at=now,
                    finished_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            repositories.batch.mark_running(batch.id)
        return batch.model_copy(update={"status": "running"})

    def run(self, adaptor_type: AdapterType, **kwargs) -> IngestionBatchRecord:
        batch = self.create_running_batch(source_name=adaptor_type, **kwargs)
        outcome: PipelineOutcome | None = None
        try:
            self._raw_store.write_manifest(
                batch,
                status="running",
                row_count_raw=0,
            )
            with RepositorySession(self._database, transactional=True) as repositories:
                outcome = self._process(repositories, batch, adaptor_type, **kwargs)
            finished_at = format_timestamp()
            with RepositorySession(self._database, transactional=True) as repositories:
                self._persist_outcome(
                    repositories,
                    batch=batch,
                    outcome=outcome,
                    finished_at=finished_at,
                )
            self._raw_store.write_manifest(
                batch,
                status=outcome.status,
                row_count_raw=outcome.raw_count,
                rejected=outcome.rejected_records,
                finished_at=finished_at,
            )
            return batch.model_copy(
                update={
                    "status": outcome.status,
                    "finished_at": finished_at,
                    "raw_count": outcome.raw_count,
                    "valid_count": outcome.valid_count,
                    "loaded_count": outcome.loaded_count,
                    "rejected_count": outcome.rejected_count,
                    "error_summary": outcome.error_summary,
                    "updated_at": finished_at,
                }
            )
        except Exception as exc:
            finished_at = format_timestamp()
            raw_count = outcome.raw_count if outcome is not None else 0
            with RepositorySession(self._database, transactional=True) as repositories:
                repositories.batch.complete_batch(
                    batch_id=batch.id,
                    status="failed",
                    finished_at=finished_at,
                    raw_count=raw_count,
                    valid_count=0,
                    loaded_count=0,
                    rejected_count=0,
                    error_summary=str(exc),
                )
            try:
                self._raw_store.write_manifest(
                    batch,
                    status="failed",
                    row_count_raw=raw_count,
                    finished_at=finished_at,
                )
            except Exception:
                pass
            raise PipelineExecutionError(str(exc)) from exc

    def _process(
        self,
        repositories: RepositorySession,
        batch: IngestionBatchRecord,
        adaptor_type: AdapterType,
        **kwargs: Any,
    ) -> PipelineOutcome:
        raise NotImplementedError

    @classmethod
    def _persist_outcome(
        cls,
        repositories: RepositorySession,
        *,
        batch: IngestionBatchRecord,
        outcome: PipelineOutcome,
        finished_at: str,
    ) -> None:
        repositories.batch.complete_batch(
            batch_id=batch.id,
            status=outcome.status,
            finished_at=finished_at,
            raw_count=outcome.raw_count,
            valid_count=outcome.valid_count,
            loaded_count=outcome.loaded_count,
            rejected_count=outcome.rejected_count,
            error_summary=outcome.error_summary,
        )
