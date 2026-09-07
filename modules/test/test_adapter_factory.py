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


class AdapterFactoryTest(unittest.TestCase):
    def test_factory_returns_akshare_fetchers(self) -> None:
        self.assertIsInstance(create_stock_fetcher("akshare"), AkshareStockAdapter)
        self.assertIsInstance(
            create_trading_calendar_fetcher("akshare"),
            AkshareTradingCalendarAdapter,
        )
        self.assertIsInstance(
            create_stock_daily_quote_fetcher("akshare"),
            AkshareDailyQuoteAdapter,
        )

    def test_factory_rejects_unsupported_adapter_type(self) -> None:
        with self.assertRaisesRegex(Exception, "unsupported adapter type: tushare"):
            create_stock_fetcher("tushare")

        with self.assertRaisesRegex(Exception, "unsupported adapter type: tushare"):
            create_trading_calendar_fetcher("tushare")

        with self.assertRaisesRegex(Exception, "unsupported adapter type: tushare"):
            create_stock_daily_quote_fetcher("tushare")


if __name__ == "__main__":
    unittest.main()
