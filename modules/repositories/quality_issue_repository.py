from __future__ import annotations

import json
from datetime import date, datetime
from typing import Iterable

from modules.repositories.models import DataQualityIssueRecord
from modules.repositories.base import SQLiteRepository


class QualityIssueRepository(SQLiteRepository):
    def insert_many(self, issues: Iterable[DataQualityIssueRecord]) -> None:
        payload = [
            (
                issue.ingestion_batch_id,
                issue.resource_type,
                issue.severity,
                issue.issue_code,
                issue.business_key,
                issue.message,
                (
                    json.dumps(
                        issue.raw_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=_json_default,
                    )
                    if issue.raw_payload is not None
                    else None
                ),
                issue.created_at,
            )
            for issue in issues
        ]
        if not payload:
            return
        self._connection.executemany(
            """
            INSERT INTO data_quality_issue (
                ingestion_batch_id, resource_type, severity,
                issue_code, business_key, message, raw_payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ingestion_batch_id, severity, issue_code, business_key)
            DO UPDATE SET
                message = excluded.message,
                raw_payload = excluded.raw_payload,
                created_at = excluded.created_at
            """,
            payload,
        )

    def list_issue_batch_ids(
        self,
        *,
        issue_code: str,
        ingestion_batch_ids: list[int],
    ) -> set[int]:
        if not ingestion_batch_ids:
            return set()
        placeholders = ",".join("?" for _ in ingestion_batch_ids)
        rows = self._connection.execute(
            f"""
            SELECT DISTINCT ingestion_batch_id
            FROM data_quality_issue
            WHERE issue_code = ?
              AND ingestion_batch_id IN ({placeholders})
            """,
            [issue_code, *ingestion_batch_ids],
        ).fetchall()
        return {int(row["ingestion_batch_id"]) for row in rows}


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(
        f"Object of type {value.__class__.__name__} is not JSON serializable"
    )
