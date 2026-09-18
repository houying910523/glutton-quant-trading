from __future__ import annotations

import math

from modules.repositories.models import DailyQuoteRecord
from modules.utils.time_util import format_date
from modules.repositories.base import SQLiteRepository
from modules.repositories.ingestion_batch_repository import BatchRepository


class DailyQuoteRepository(SQLiteRepository):
    def upsert_many(self, records: list[DailyQuoteRecord]) -> None:
        payload = [
            (
                record.stock_id,
                format_date(record.trade_date),
                record.open,
                record.high,
                record.low,
                record.close,
                record.volume,
                record.turnover,
                record.ingestion_batch_id,
                record.ingested_at.strftime("%Y-%m-%d %H:%M:%S"),
                record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for record in records
        ]
        if not payload:
            return
        self._connection.executemany(
            """
            INSERT INTO daily_quote (
                stock_id, trade_date, open, high, low, close,
                volume, turnover, ingestion_batch_id, ingested_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock_id, trade_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                turnover = excluded.turnover,
                ingestion_batch_id = excluded.ingestion_batch_id,
                ingested_at = excluded.ingested_at,
                updated_at = excluded.updated_at
            """,
            payload,
        )

    def list_loaded_trade_dates(self, *, start_date: str, end_date: str) -> set[str]:
        rows = self._connection.execute(
            """
            SELECT DISTINCT trade_date
            FROM daily_quote
            WHERE trade_date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        ).fetchall()
        return {row["trade_date"] for row in rows}

    def get_latest_trade_date(self, *, stock_id: int) -> str | None:
        row = self._connection.execute(
            """
            SELECT MAX(trade_date) AS trade_date
            FROM daily_quote
            WHERE stock_id = ?
            """,
            (stock_id,),
        ).fetchone()
        if row is None:
            return None
        return row["trade_date"]

    def list_trade_dates_by_stock(
        self,
        *,
        stock_id: int,
        start_date: str,
        end_date: str,
    ) -> list[str]:
        rows = self._connection.execute(
            """
            SELECT trade_date
            FROM daily_quote
            WHERE stock_id = ?
              AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC
            """,
            (stock_id, start_date, end_date),
        ).fetchall()
        return [row["trade_date"] for row in rows]

    def calculate_coverage_threshold(
        self,
        *,
        before_trade_date: str,
        batch_repository: BatchRepository,
    ) -> int | None:
        baseline = batch_repository.recent_success_row_count_median(
            before_trade_date=before_trade_date,
        )
        if baseline is None:
            return None
        return math.floor(baseline * 0.98)
