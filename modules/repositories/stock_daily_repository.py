from __future__ import annotations


from modules.repositories.models import StockDailyRecord
from modules.utils.time_util import format_date
from modules.repositories.base import SQLiteRepository


class StockDailyRepository(SQLiteRepository):
    def upsert_many(self, records: list[StockDailyRecord]) -> None:
        payload = [
            (
                record.stock_id,
                format_date(record.trade_date),
                record.open,
                record.high,
                record.low,
                record.close,
                record.volume,
                record.amount,
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
            INSERT INTO stock_daily (
                stock_id, trade_date, open, high, low, close,
                volume, amount, turnover, ingestion_batch_id, ingested_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock_id, trade_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                amount = excluded.amount,
                turnover = excluded.turnover,
                ingestion_batch_id = excluded.ingestion_batch_id,
                ingested_at = excluded.ingested_at,
                updated_at = excluded.updated_at
            """,
            payload,
        )

    def get_latest_trade_date(self, *, stock_id: int) -> str | None:
        row = self._connection.execute(
            """
            SELECT MAX(trade_date) AS trade_date
            FROM stock_daily
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
            FROM stock_daily
            WHERE stock_id = ?
              AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC
            """,
            (stock_id, start_date, end_date),
        ).fetchall()
        return [row["trade_date"] for row in rows]

    def list_stock_daily(
        self, stock_id: int, start_date: str, end_date: str
    ) -> list[StockDailyRecord]:
        rows = self._connection.execute(
            """
            SELECT
                stock_id,
                trade_date,
                open,
                high,
                low,
                close,
                volume,
                amount,
                turnover
            FROM stock_daily
            WHERE stock_id = ?
              AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            (stock_id, start_date, end_date),
        ).fetchall()
        return [StockDailyRecord(**row) for row in rows]
