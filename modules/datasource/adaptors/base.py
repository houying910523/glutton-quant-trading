from __future__ import annotations

from typing import Literal, Protocol

from modules.repositories.models import StockInfoRecord, StockDailyRecord

AdapterType = Literal["akshare", "tushare"]


class StockFetcher(Protocol):
    def fetch(self) -> list[StockInfoRecord]: ...


class TradingCalendarFetcher(Protocol):
    def fetch(self, start_date: str, end_date: str) -> list[str]: ...


class StockDailyQuoteFetcher(Protocol):
    def fetch(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        stock_id: int,
        batch_id: int,
    ) -> list[StockDailyRecord]: ...


def create_stock_fetcher(
    adapter_type: AdapterType,
) -> StockFetcher:
    if adapter_type == "akshare":
        from modules.datasource.adaptors.akshare import (
            AkshareStockAdapter,
        )

        return AkshareStockAdapter()
    else:
        raise Exception(f"unsupported adapter type: {adapter_type}")


def create_trading_calendar_fetcher(
    adapter_type: AdapterType,
) -> TradingCalendarFetcher:
    if adapter_type == "akshare":
        from modules.datasource.adaptors.akshare import AkshareTradingCalendarAdapter

        return AkshareTradingCalendarAdapter()
    else:
        raise Exception(f"unsupported adapter type: {adapter_type}")


def create_stock_daily_quote_fetcher(
    adapter_type: AdapterType,
) -> StockDailyQuoteFetcher:
    if adapter_type == "akshare":
        from modules.datasource.adaptors.akshare import AkshareDailyQuoteAdapter

        return AkshareDailyQuoteAdapter()
    else:
        raise Exception(f"unsupported adapter type: {adapter_type}")
