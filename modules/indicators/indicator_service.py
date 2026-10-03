from __future__ import annotations

from dataclasses import dataclass

import polars as pl
import duckdb

from modules.indicators.storage import IndicatorStore
from modules.indicators.storage.path_resolver import resolve_partition_glob
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import IndicatorRecord, StockInfoRecord
from modules.repositories.session import RepositorySession
from modules.utils.time_util import format_date


@dataclass(frozen=True)
class _DatasetSelection:
    indicator: IndicatorRecord
    columns: list[str]


class IndicatorService:
    def __init__(self, database: SQLiteDatabase, store: IndicatorStore):
        self._database = database
        self._store = store

    def get_indicator_dataset(
        self,
        stock_info: StockInfoRecord,
        start_date: str,
        end_date: str,
        names: list[str],
    ) -> pl.DataFrame:
        normalized_start = format_date(start_date)
        normalized_end = format_date(end_date)
        if normalized_start is None or normalized_end is None:
            raise ValueError("start_date and end_date are required")

        if not names:
            return self._empty_frame([])

        with RepositorySession(self._database) as session:
            indicators = session.indicator.list_active()

        selections, output_columns = self._resolve_selections(indicators, names)
        if not selections:
            return self._empty_frame(output_columns)

        existing_selections: list[_DatasetSelection] = []
        for selection in selections:
            if self._store.exists(storage_key=selection.indicator.storage_key):
                existing_selections.append(selection)

        if not existing_selections:
            return self._empty_frame(output_columns)

        frame = self._query_dataset(
            existing_selections,
            instrument_id=stock_info.instrument_id,
            start_date=normalized_start,
            end_date=normalized_end,
            output_columns=output_columns,
        )
        if frame.is_empty():
            return self._empty_frame(output_columns)

        missing_columns = [
            column for column in output_columns if column not in frame.columns
        ]
        if missing_columns:
            frame = frame.with_columns(
                [
                    pl.lit(None).cast(pl.Float64).alias(column)
                    for column in missing_columns
                ]
            )

        return frame.select(["trade_date", "instrument_id", *output_columns]).sort(
            ["trade_date", "instrument_id"]
        )

    @classmethod
    def _resolve_selections(
        cls,
        indicators: list[IndicatorRecord],
        names: list[str],
    ) -> tuple[list[_DatasetSelection], list[str]]:
        output_columns: list[str] = []
        indicators_mapping = {indicator.id: indicator for indicator in indicators}
        name_to_indicator: dict[str, IndicatorRecord] = {
            name: indicator
            for indicator in indicators
            for name in indicator.output_columns
            if name in names
        }
        indicator_to_columns: dict[int, list[str]] = {}

        for name, indicator in name_to_indicator.items():
            indicator_to_columns.setdefault(indicator.id, []).append(name)
            output_columns.append(name)

        selections = [
            _DatasetSelection(
                indicator=indicators_mapping[indicator_id],
                columns=columns,
            )
            for indicator_id, columns in indicator_to_columns.items()
        ]
        return selections, output_columns

    def _query_dataset(
        self,
        selections: list[_DatasetSelection],
        *,
        instrument_id: str,
        start_date: str,
        end_date: str,
        output_columns: list[str],
    ) -> pl.DataFrame:
        ctes: list[str] = []
        selected_columns: list[str] = []
        parameters: list[str] = []

        for index, selection in enumerate(selections):
            alias = f"q{index}"
            parquet_glob = resolve_partition_glob(
                self._store.indicator_root,
                selection.indicator.storage_key,
            )
            indicator_columns = ", ".join(
                self._quote_identifier(column) for column in selection.columns
            )
            ctes.append(
                f"""
                {alias} AS (
                    SELECT
                        CAST(trade_date AS DATE) AS trade_date,
                        instrument_id,
                        {indicator_columns}
                    FROM read_parquet('{parquet_glob}')
                    WHERE instrument_id = ?
                      AND CAST(trade_date AS DATE) BETWEEN ? AND ?
                )
                """.strip()
            )
            parameters.extend([instrument_id, start_date, end_date])
            selected_columns.extend(
                f"{alias}.{self._quote_identifier(column)} AS {self._quote_identifier(column)}"
                for column in selection.columns
            )

        from_clause = "q0"
        for index in range(1, len(selections)):
            from_clause += (
                f" FULL OUTER JOIN q{index} USING (trade_date, instrument_id)"
            )

        query = f"""
            WITH {", ".join(ctes)}
            SELECT
                trade_date,
                instrument_id,
                {", ".join(selected_columns)}
            FROM {from_clause}
            ORDER BY trade_date ASC, instrument_id ASC
        """

        connection = duckdb.connect(database=":memory:")
        try:
            result = (
                connection.execute(query, parameters)
                .fetch_df()
                .to_dict(orient="records")
            )
        finally:
            connection.close()

        frame = pl.DataFrame(result)
        if frame.is_empty():
            return self._empty_frame(output_columns)
        if "trade_date" in frame.columns:
            frame = frame.with_columns(pl.col("trade_date").cast(pl.Date, strict=False))
        return frame

    @classmethod
    def _empty_frame(cls, output_columns: list[str]) -> pl.DataFrame:
        schema: dict[str, pl.DataType] = {
            "trade_date": pl.Date(),
            "instrument_id": pl.Utf8(),
        }
        for column in output_columns:
            schema[column] = pl.Float64()
        return pl.DataFrame(schema=schema)

    @classmethod
    def _quote_identifier(cls, value: str) -> str:
        return '"' + value + '"'
