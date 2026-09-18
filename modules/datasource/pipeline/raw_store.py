from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.config import DEFAULT_RAW_ROOT, resolve_project_path
from modules.repositories.models import IngestionBatchRecord, RawManifestRecord


class RawStore:
    default_raw_root = resolve_project_path(DEFAULT_RAW_ROOT)

    def __init__(self, root_path: str | Path = default_raw_root) -> None:
        self._root_path = Path(root_path)

    def batch_directory(self, batch: IngestionBatchRecord) -> Path:
        ingest_date = batch.started_at.split(" ", 1)[0]
        return (
            self._root_path
            / batch.source_name
            / batch.resource_type
            / f"ingest_date={ingest_date}"
            / f"ingestion_batch_key={batch.batch_key}"
        )

    def write_manifest(
        self,
        batch: IngestionBatchRecord,
        *,
        status: str,
        row_count_raw: int,
        rejected: list[Any] | None = None,
        finished_at: str | None = None,
    ) -> Path:
        directory = self.batch_directory(batch)
        directory.mkdir(parents=True, exist_ok=True)
        manifest = RawManifestRecord(
            ingestion_batch_id=batch.id,
            batch_key=batch.batch_key or "",
            source_name=batch.source_name,
            resource_type=batch.resource_type,
            sync_mode=batch.sync_mode,
            request_params={
                "resource_type": batch.resource_type,
                "sync_mode": batch.sync_mode,
                "start_date": batch.start_date,
                "end_date": batch.end_date,
                "rejected": rejected or [],
            },
            started_at=batch.started_at,
            finished_at=finished_at,
            row_count_raw=row_count_raw,
            status=status,
        )
        manifest_path = directory / "manifest.json"
        manifest_path.write_text(
            manifest.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )
        return manifest_path
