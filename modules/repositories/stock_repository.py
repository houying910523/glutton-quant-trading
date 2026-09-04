from __future__ import annotations

from typing import Iterable

from modules.repositories.models import StockRecord
from modules.datasource.shared import format_date
from modules.repositories.base import SQLiteRepository


class StockRepository(SQLiteRepository):
    def upsert_many(self, records: list[StockRecord]) -> None:
        payload = [
            (
                record.market,
                record.exchange,
                record.symbol,
                record.ticker,
                record.name,
                record.asset_type,
                record.currency,
                record.lot_size,
                format_date(record.listed_at),
                format_date(record.delisted_at),
                record.status,
                record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for record in records
        ]
        if not payload:
            return
        self._connection.executemany(
            """
            INSERT INTO stock (
                market, exchange, symbol, ticker, name, asset_type, currency,
                lot_size, listed_at, delisted_at, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market, exchange, symbol) DO UPDATE SET
                ticker = excluded.ticker,
                name = excluded.name,
                lot_size = excluded.lot_size,
                listed_at = excluded.listed_at,
                delisted_at = excluded.delisted_at,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            payload,
        )

    def load_existing_by_natural_keys(
        self,
        keys: Iterable[tuple[str, str, str]],
    ) -> dict[tuple[str, str, str], object]:
        key_list = list(keys)
        if not key_list:
            return {}
        placeholders = ",".join("(?, ?, ?)" for _ in key_list)
        parameters: list[str] = []
        for market, exchange, symbol in key_list:
            parameters.extend([market, exchange, symbol])
        rows = self._connection.execute(
            f"""
            SELECT *
            FROM stock
            WHERE (market, exchange, symbol) IN ({placeholders})
            """,
            parameters,
        ).fetchall()
        return {(row["market"], row["exchange"], row["symbol"]): row for row in rows}

    def list_active_symbols(self) -> list[tuple[int, str]]:
        rows = self._connection.execute(
            """
            SELECT id, symbol
            FROM stock
            WHERE status = 'active'
            ORDER BY exchange ASC, symbol ASC
            """
        ).fetchall()
        return [
            (
                row["id"],
                row["symbol"],
            )
            for row in rows
        ]
