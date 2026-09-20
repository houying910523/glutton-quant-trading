from __future__ import annotations

import sqlite3

from modules.repositories.database import SQLiteDatabase


class RepositorySession:
    def __init__(
        self, database: SQLiteDatabase, *, transactional: bool = False
    ) -> None:
        self._database = database
        self._transactional = transactional
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> "RepositorySession":
        from modules.repositories.stock_daily_repository import StockDailyRepository
        from modules.repositories.indicator_repository import (
            IndicatorRepository,
        )
        from modules.repositories.ingestion_batch_repository import BatchRepository
        from modules.repositories.stock_info_repository import StockInfoRepository
        from modules.repositories.trading_calendar_repository import (
            TradingCalendarRepository,
        )

        connection = self._database.connect()
        if connection is None:
            raise Exception("连接数据库失败")
        self.batch = BatchRepository(connection)
        self.stock_daily = StockDailyRepository(connection)
        self.stock_info = StockInfoRepository(connection)
        self.trading_calendar = TradingCalendarRepository(connection)
        self.indicator = IndicatorRepository(connection)
        self._connection = connection
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._connection is not None
        try:
            if self._transactional:
                if exc is None:
                    self._connection.commit()
                else:
                    self._connection.rollback()
        finally:
            self._connection.close()

    def commit(self) -> None:
        if self._transactional:
            self._connection.commit()
