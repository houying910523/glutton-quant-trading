from __future__ import annotations

from modules.repositories.models import TradingCalendarRecord
from modules.utils.time_util import format_date
from modules.repositories.base import SQLiteRepository


class TradingCalendarRepository(SQLiteRepository):
    def get_latest_trade_date(self) -> str | None:
        row = self._connection.execute(
            """
            SELECT trade_date
            FROM trading_calendar
            WHERE market = 'CN'
            ORDER BY trade_date DESC
            LIMIT 1
            """
        ).fetchone()
        return row["trade_date"] if row else None

    def upsert_many(self, records: list[TradingCalendarRecord]) -> None:
        payload = [
            (
                record.market,
                format_date(record.trade_date),
                int(record.is_open),
                record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for record in records
        ]
        if not payload:
            return
        self._connection.executemany(
            """
            INSERT INTO trading_calendar (
                market, trade_date, is_open, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(market, trade_date) DO UPDATE SET
                is_open = excluded.is_open,
                updated_at = excluded.updated_at
            """,
            payload,
        )

    def list_open_trade_dates(self, *, start_date: str, end_date: str) -> list[str]:
        rows = self._connection.execute(
            """
            SELECT trade_date
            FROM trading_calendar
            WHERE market = 'CN'
              AND is_open = 1
              AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC
            """,
            (start_date, end_date),
        ).fetchall()
        return [row["trade_date"] for row in rows]

    def list_recent_open_trade_dates(self, *, end_date: str, limit: int) -> list[str]:
        if limit <= 0:
            return []
        rows = self._connection.execute(
            """
            SELECT trade_date
            FROM trading_calendar
            WHERE market = 'CN'
              AND is_open = 1
              AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (end_date, limit),
        ).fetchall()
        return [row["trade_date"] for row in reversed(rows)]
