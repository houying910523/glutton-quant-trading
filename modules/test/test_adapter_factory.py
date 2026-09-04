from __future__ import annotations

import unittest

from modules.datasource.adaptors import create_adapter, get_adapter_source_name
from modules.datasource.adaptors.akshare import (
    AkshareDailyQuoteAdapter,
    AkshareStockAdapter,
    AkshareTradingCalendarAdapter,
)
from modules.test.test_akshare_adapters import FakeAkshareClient


class AdapterFactoryTest(unittest.TestCase):
    def test_create_adapter_returns_akshare_adapter_by_default_type(self) -> None:
        self.assertIsInstance(
            create_adapter(
                "akshare",
                "stock",
                "stock_2026-09-03_001",
                client=FakeAkshareClient(),
            ),
            AkshareStockAdapter,
        )
        self.assertIsInstance(
            create_adapter(
                "akshare",
                "trading_calendar",
                "calendar_2026-09-03_001",
                client=FakeAkshareClient(),
            ),
            AkshareTradingCalendarAdapter,
        )
        self.assertIsInstance(
            create_adapter(
                "akshare",
                "daily_quote",
                "daily_quote_2026-09-03_001",
                client=FakeAkshareClient(),
                max_workers=1,
            ),
            AkshareDailyQuoteAdapter,
        )

    def test_get_adapter_source_name(self) -> None:
        self.assertEqual(get_adapter_source_name("akshare"), "akshare")
        self.assertEqual(get_adapter_source_name("tushare"), "tushare_pro")


if __name__ == "__main__":
    unittest.main()
