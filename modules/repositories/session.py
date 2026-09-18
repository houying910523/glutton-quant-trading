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
        from modules.repositories.daily_quote_repository import DailyQuoteRepository
        from modules.repositories.factor_definition_repository import (
            FactorDefinitionRepository,
        )
        from modules.repositories.ingestion_batch_repository import BatchRepository
        from modules.repositories.stock_repository import StockRepository
        from modules.repositories.trading_calendar_repository import (
            TradingCalendarRepository,
        )

        connection = self._database.connect()
        if connection is None:
            raise Exception("连接数据库失败")
        self.batch = BatchRepository(connection)
        self.daily_quote = DailyQuoteRepository(connection)
        self.factor_definition = FactorDefinitionRepository(connection)
        self.stock = StockRepository(connection)
        self.trading_calendar = TradingCalendarRepository(connection)
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
