from __future__ import annotations

import json
from uuid import uuid4

from modules.utils.time_util import format_timestamp
from modules.repositories.base import SQLiteRepository
from modules.repositories.models import IngestionBatchRecord


class BatchRepository(SQLiteRepository):
    def create_batch(
        self,
        record: IngestionBatchRecord,
    ) -> IngestionBatchRecord:
        now = format_timestamp()
        batch_date = now.split(" ", 1)[0]
        batch_key = self._next_batch_key(record.resource_type, batch_date)
        retry_count = self._retry_count(record)
        cursor = self._connection.execute(
            """
            INSERT INTO ingestion_batch (
                batch_key, source_name, resource_type, sync_mode,
                start_date, end_date, request_params, status,
                started_at, finished_at, raw_count, valid_count,
                loaded_count, rejected_count, retry_count,
                error_summary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_key,
                record.source_name,
                record.resource_type,
                record.sync_mode,
                record.start_date,
                record.end_date,
                json.dumps(record.request_params, ensure_ascii=False),
                "pending",
                now,
                None,
                0,
                0,
                0,
                0,
                retry_count,
                None,
                now,
                now,
            ),
        )
        return IngestionBatchRecord(
            id=int(cursor.lastrowid),
            batch_key=batch_key,
            source_name=record.source_name,
            resource_type=record.resource_type,
            sync_mode=record.sync_mode,
            start_date=record.start_date,
            end_date=record.end_date,
            request_params=record.request_params,
            status="pending",
            started_at=now,
            finished_at=None,
            raw_count=0,
            valid_count=0,
            loaded_count=0,
            rejected_count=0,
            retry_count=retry_count,
            error_summary=None,
            created_at=now,
            updated_at=now,
        )

    def mark_running(self, batch_id: int) -> None:
        self._connection.execute(
            """
            UPDATE ingestion_batch
            SET status = 'running', updated_at = ?
            WHERE id = ?
            """,
            (format_timestamp(), batch_id),
        )

    def complete_batch(
        self,
        *,
        batch_id: int,
        status: str,
        finished_at: str,
        raw_count: int,
        valid_count: int,
        loaded_count: int,
        rejected_count: int,
        error_summary: str | None,
    ) -> None:
        self._connection.execute(
            """
            UPDATE ingestion_batch
            SET status = ?,
                finished_at = ?,
                raw_count = ?,
                valid_count = ?,
                loaded_count = ?,
                rejected_count = ?,
                error_summary = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                finished_at,
                raw_count,
                valid_count,
                loaded_count,
                rejected_count,
                error_summary,
                finished_at,
                batch_id,
            ),
        )

    def _next_batch_key(self, resource_type: str, batch_date: str) -> str:
        prefix = f"{resource_type}_{batch_date}_"
        return f"{prefix}{uuid4().hex[:8]}"

    def _retry_count(self, record: IngestionBatchRecord) -> int:
        count = self._connection.execute(
            """
            SELECT COUNT(*)
            FROM ingestion_batch
            WHERE resource_type = ?
              AND sync_mode = ?
              AND IFNULL(start_date, '') = IFNULL(?, '')
              AND IFNULL(end_date, '') = IFNULL(?, '')
              AND status = 'failed'
            """,
            (
                record.resource_type,
                record.sync_mode,
                record.start_date,
                record.end_date,
            ),
        ).fetchone()[0]
        return int(count)
