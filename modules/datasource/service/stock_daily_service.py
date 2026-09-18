from __future__ import annotations

from datetime import date

import polars as pl

from modules.repositories.database import SQLiteDatabase


class StockDailyService:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def load_daily_bars(
        self,
        *,
        start_date: date,
        end_date: date,
        instruments: list[str] | None = None,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        return self.load_stock_daily(
            start_date=start_date,
            end_date=end_date,
            instruments=instruments,
            columns=columns,
        )

    def load_stock_daily(
        self,
        *,
        start_date: date,
        end_date: date,
        instruments: list[str] | None = None,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        requested = self._normalize_columns(columns)
        select_items = [
            "q.trade_date AS trade_date",
            self._instrument_id_sql() + " AS instrument_id",
        ]
        select_items.extend(self._column_sql(column) for column in requested)

        sql = f"""
            SELECT {", ".join(select_items)}
            FROM daily_quote q
            JOIN stock s
              ON s.id = q.stock_id
            WHERE q.trade_date BETWEEN ? AND ?
        """
        parameters: list[object] = [start_date.isoformat(), end_date.isoformat()]

        if instruments:
            placeholders = ",".join("?" for _ in instruments)
            sql += f" AND {self._instrument_id_sql()} IN ({placeholders})"
            parameters.extend(instruments)

        sql += " ORDER BY q.trade_date ASC, instrument_id ASC"

        with self._database.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()

        if not rows:
            return self._empty_frame(requested)

        frame = pl.DataFrame([dict(row) for row in rows])
        return frame.with_columns(
            pl.col("trade_date").str.strptime(pl.Date, "%Y-%m-%d", strict=False)
        )

    @classmethod
    def _normalize_columns(cls, columns: list[str] | None) -> list[str]:
        default_columns = ["open", "high", "low", "close", "volume", "turnover"]
        if columns is None:
            return default_columns
        allowed = set(default_columns)
        normalized = []
        for column in columns:
            if column not in allowed:
                raise ValueError(f"unsupported daily bar column: {column}")
            if column not in normalized:
                normalized.append(column)
        return normalized

    @classmethod
    def _column_sql(cls, column: str) -> str:
        mapping = {
            "open": "q.open / 100.0 AS open",
            "high": "q.high / 100.0 AS high",
            "low": "q.low / 100.0 AS low",
            "close": "q.close / 100.0 AS close",
            "volume": "q.volume AS volume",
            "turnover": "CASE WHEN q.turnover IS NULL THEN NULL ELSE q.turnover / 100.0 END AS turnover",
        }
        return mapping[column]

    @classmethod
    def _instrument_id_sql(cls) -> str:
        return (
            "CASE "
            "WHEN s.exchange = 'SSE' THEN s.symbol || '.SH' "
            "WHEN s.exchange = 'SZSE' THEN s.symbol || '.SZ' ELSE s.symbol "
            "END"
        )

    @classmethod
    def _empty_frame(cls, requested: list[str]) -> pl.DataFrame:
        schema: dict[str, pl.DataType] = {
            "trade_date": pl.Date,
            "instrument_id": pl.Utf8,
        }
        for column in requested:
            if column == "volume":
                schema[column] = pl.Int64
            else:
                schema[column] = pl.Float64
        return pl.DataFrame(schema=schema)
