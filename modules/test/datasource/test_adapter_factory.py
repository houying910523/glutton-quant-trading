from __future__ import annotations

import unittest

from modules.datasource.adaptors.akshare import (
    AkshareDailyQuoteAdapter,
    AkshareStockAdapter,
    AkshareTradingCalendarAdapter,
)
from modules.datasource.adaptors.base import (
    create_stock_daily_quote_fetcher,
    create_stock_fetcher,
    create_trading_calendar_fetcher,
)


class CreateStockFetcherTest(unittest.TestCase):
    def test_create_stock_fetcher_returns_akshare_fetcher(self) -> None:
        self.assertIsInstance(create_stock_fetcher("akshare"), AkshareStockAdapter)

    def test_create_stock_fetcher_rejects_unsupported_adapter_type(self) -> None:
        with self.assertRaisesRegex(Exception, "unsupported adapter type: tushare"):
            create_stock_fetcher("tushare")


class CreateTradingCalendarFetcherTest(unittest.TestCase):
    def test_create_trading_calendar_fetcher_returns_akshare_fetcher(self) -> None:
        self.assertIsInstance(
            create_trading_calendar_fetcher("akshare"),
            AkshareTradingCalendarAdapter,
        )

    def test_create_trading_calendar_fetcher_rejects_unsupported_adapter_type(
        self,
    ) -> None:
        with self.assertRaisesRegex(Exception, "unsupported adapter type: tushare"):
            create_trading_calendar_fetcher("tushare")


class CreateStockDailyQuoteFetcherTest(unittest.TestCase):
    def test_create_stock_daily_quote_fetcher_returns_akshare_fetcher(self) -> None:
        self.assertIsInstance(
            create_stock_daily_quote_fetcher("akshare"),
            AkshareDailyQuoteAdapter,
        )

    def test_create_stock_daily_quote_fetcher_rejects_unsupported_adapter_type(
        self,
    ) -> None:
        with self.assertRaisesRegex(Exception, "unsupported adapter type: tushare"):
            create_stock_daily_quote_fetcher("tushare")


if __name__ == "__main__":
    unittest.main()
