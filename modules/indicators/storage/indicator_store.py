from __future__ import annotations

from glob import glob
from pathlib import Path

import polars as pl

from modules.indicators.storage.path_resolver import (
    resolve_dataset_root,
    resolve_partition_glob,
    resolve_partition_path,
)


class IndicatorStore:
    def __init__(self, indicator_root: Path) -> None:
        self._indicator_root = Path(indicator_root)

    @property
    def indicator_root(self) -> Path:
        return self._indicator_root

    def dataset_root(self, storage_key: str) -> Path:
        return resolve_dataset_root(self._indicator_root, storage_key)

    def partition_path(self, storage_key: str, *, year: int, month: int) -> Path:
        return resolve_partition_path(
            self._indicator_root,
            storage_key,
            year=year,
            month=month,
        )

    def write_month_partition(
        self,
        *,
        storage_key: str,
        frame: pl.DataFrame,
        year: int,
        month: int,
    ) -> Path:
        path = self.partition_path(storage_key, year=year, month=month)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(path)
        return path

    def read_dataset(
        self,
        *,
        storage_key: str,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        pattern = resolve_partition_glob(self._indicator_root, storage_key)
        paths = sorted(Path(path) for path in glob(pattern))
        if not paths:
            return pl.DataFrame()
        return pl.read_parquet([str(path) for path in paths], columns=columns)

    def list_partition_paths(self, *, storage_key: str) -> list[Path]:
        dataset_root = self.dataset_root(storage_key)
        return sorted(dataset_root.glob("year=*/month=*/data.parquet"))

    def exists(self, *, storage_key: str) -> bool:
        return any(self.list_partition_paths(storage_key=storage_key))

    def delete_dataset(self, *, storage_key: str) -> None:
        dataset_root = self.dataset_root(storage_key)
        if not dataset_root.exists():
            return
        for path in sorted(dataset_root.glob("**/*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if dataset_root.exists():
            dataset_root.rmdir()
