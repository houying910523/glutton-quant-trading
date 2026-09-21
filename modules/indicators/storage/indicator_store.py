from __future__ import annotations

from pathlib import Path

import polars as pl

from modules.indicators.storage.path_resolver import (
    resolve_dataset_root,
    resolve_partition_path,
)

_STRING_DTYPES = {pl.Utf8}
if hasattr(pl, "String"):
    _STRING_DTYPES.add(pl.String)


class IndicatorStore:
    def __init__(self, indicator_root: Path) -> None:
        self._indicator_root = Path(indicator_root)

    @property
    def indicator_root(self) -> Path:
        return self._indicator_root

    def dataset_root(self, storage_key: str) -> Path:
        return resolve_dataset_root(self._indicator_root, storage_key)

    def partition_path(self, storage_key: str, *, year: int) -> Path:
        return resolve_partition_path(
            self._indicator_root,
            storage_key,
            year=year,
        )

    def write_year_partition(
        self,
        *,
        storage_key: str,
        frame: pl.DataFrame,
        year: int,
    ) -> Path:
        path = self.partition_path(storage_key, year=year)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._prepare_frame_for_write(frame).write_parquet(path)
        return path

    def read_year_partition(
        self,
        *,
        storage_key: str,
        year: int,
    ) -> pl.DataFrame | None:
        path = self.partition_path(storage_key, year=year)
        if not path.exists():
            return None
        return self._read_parquet(path)

    def read_dataset(
        self,
        *,
        storage_key: str,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        paths = self.list_partition_paths(storage_key=storage_key)
        if not paths:
            return pl.DataFrame()
        return self._read_parquet([str(path) for path in paths], columns=columns)

    def list_partition_paths(self, *, storage_key: str) -> list[Path]:
        dataset_root = self.dataset_root(storage_key)
        return sorted(dataset_root.glob("year=*/data.parquet"))

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

    @classmethod
    def _prepare_frame_for_write(cls, frame: pl.DataFrame) -> pl.DataFrame:
        if "trade_date" not in frame.columns:
            return frame

        trade_date_dtype = frame.schema.get("trade_date")
        if trade_date_dtype in _STRING_DTYPES:
            return frame
        if trade_date_dtype in (pl.Date, pl.Datetime):
            return frame.with_columns(
                pl.col("trade_date").dt.strftime("%Y-%m-%d").alias("trade_date")
            )
        raise ValueError(
            "trade_date must be Date, Datetime, or String before writing parquet"
        )

    @classmethod
    def _read_parquet(
        cls,
        source: str | Path | list[str],
        *,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        return cls._normalize_frame_after_read(pl.read_parquet(source, columns=columns))

    @classmethod
    def _normalize_frame_after_read(cls, frame: pl.DataFrame) -> pl.DataFrame:
        if "trade_date" not in frame.columns:
            return frame

        trade_date_dtype = frame.schema.get("trade_date")
        if trade_date_dtype in _STRING_DTYPES:
            return frame.with_columns(
                pl.col("trade_date")
                .str.strptime(pl.Date, "%Y-%m-%d", strict=False)
                .alias("trade_date")
            )
        return frame
