from __future__ import annotations

from typing import Iterable

from modules.repositories.models import StockInfoRecord
from modules.utils.time_util import format_date
from modules.repositories.base import SQLiteRepository


class StockInfoRepository(SQLiteRepository):
    def get(self, stock_id: int) -> StockInfoRecord | None:
        row = self._connection.execute(
            """
            SELECT * FROM stock_info WHERE id = ?
            """,
            (stock_id,),
        ).fetchone()
        if row is None:
            return None
        return StockInfoRecord(**row)

    def upsert_many(self, records: list[StockInfoRecord]) -> None:
        payload = [
            (
                record.market,
                record.exchange,
                record.symbol,
                record.ticker,
                record.name,
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
            INSERT INTO stock_info (
                market, exchange, symbol, ticker, name, currency,
                lot_size, listed_at, delisted_at, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            FROM stock_info
            WHERE (market, exchange, symbol) IN ({placeholders})
            """,
            parameters,
        ).fetchall()
        return {(row["market"], row["exchange"], row["symbol"]): row for row in rows}

    def list_active_sync_targets(
        self,
        *,
        stock_ids: list[int] | None = None,
        symbols: list[str] | None = None,
    ) -> list[tuple[int, str, str | None]]:
        conditions = ["status = 'active'"]
        parameters: list[object] = []

        if stock_ids:
            conditions.append(f"id IN ({','.join('?' for _ in stock_ids)})")
            parameters.extend(stock_ids)

        if symbols:
            conditions.append(f"symbol IN ({','.join('?' for _ in symbols)})")
            parameters.extend(symbols)

        rows = self._connection.execute(
            f"""
            SELECT id, symbol, listed_at
            FROM stock_info
            WHERE {" AND ".join(conditions)}
            ORDER BY exchange ASC, symbol ASC
            """,
            parameters,
        ).fetchall()
        return [
            (
                row["id"],
                row["symbol"],
                row["listed_at"],
            )
            for row in rows
        ]

    def list_symbols(
        self, symbol: str, name: str, page_no: int = 1, page_size: int = 40
    ) -> list[StockInfoRecord]:
        conditions = ["status = 'active'"]
        parameters: list[object] = []
        if symbol:
            conditions.append("symbol LIKE ?")
            parameters.append(f"%{symbol}%")
        if name:
            conditions.append("name LIKE ?")
            parameters.append(f"%{name}%")

        parameters.append((page_no - 1) * page_size)
        parameters.append(page_size)

        rows = self._connection.execute(
            f"""
                   SELECT id, symbol, listed_at, name, ticker, market, exchange, updated_at, created_at
                   FROM stock_info
                   WHERE {" AND ".join(conditions)}
                   ORDER BY id ASC
                   LIMIT ?, ?
                   """,
            parameters,
        ).fetchall()
        return [
            StockInfoRecord(
                id=row["id"],
                symbol=row["symbol"],
                listed_at=row["listed_at"],
                status="active",
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                market=row["market"],
                exchange=row["exchange"],
                ticker=row["ticker"],
                name=row["name"],
            )
            for row in rows
        ]
