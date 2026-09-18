from __future__ import annotations

from pathlib import Path


def _normalize_storage_key(storage_key: str) -> Path:
    normalized = storage_key.strip().strip("/")
    if not normalized:
        raise ValueError("storage_key must not be empty")
    candidate = Path(normalized)
    if candidate.is_absolute():
        raise ValueError("storage_key must be a relative path")
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("storage_key must not contain '.', '..', or empty segments")
    return candidate


def resolve_dataset_root(indicator_root: Path, storage_key: str) -> Path:
    return Path(indicator_root) / _normalize_storage_key(storage_key)


def resolve_partition_path(
    indicator_root: Path,
    storage_key: str,
    *,
    year: int,
    month: int,
) -> Path:
    if year <= 0:
        raise ValueError("year must be positive")
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    return (
        resolve_dataset_root(indicator_root, storage_key)
        / f"year={year:04d}"
        / f"month={month:02d}"
        / "data.parquet"
    )


def resolve_partition_glob(indicator_root: Path, storage_key: str) -> str:
    return str(
        resolve_dataset_root(indicator_root, storage_key)
        / "year=*"
        / "month=*"
        / "data.parquet"
    )
