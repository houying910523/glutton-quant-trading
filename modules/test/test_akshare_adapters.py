from __future__ import annotations

import unittest

from modules.datasource.adaptors.akshare import (
    AkshareDailyQuoteAdapter,
    AkshareStockAdapter,
    AkshareTradingCalendarAdapter,
)
from modules.datasource.shared import ConfigurationError, FetchRequest


class FakeFrame:
    def __init__(self, rows):
        self._rows = rows

    def to_dict(self, orient: str):
        if orient != "records":
            raise AssertionError(f"unexpected orient: {orient}")
        return list(self._rows)


class FakeAkshareClient:
    def __init__(self):
        self.calls = []

    def tool_trade_date_hist_sina(self):
        self.calls.append(("tool_trade_date_hist_sina", {}))
        return FakeFrame([{"trade_date": "2024-08-26"}, {"trade_date": "2024-08-27"}])

    def stock_info_sh_name_code(self, symbol: str = "主板A股"):
        self.calls.append(("stock_info_sh_name_code", {"symbol": symbol}))
        return FakeFrame(
            [
                {
                    "证券代码": "600519",
                    "证券简称": "贵州茅台",
                    "上市日期": "2001-08-27",
                }
            ]
        )

    def stock_info_sz_name_code(self, symbol: str = "A股列表"):
        self.calls.append(("stock_info_sz_name_code", {"symbol": symbol}))
        return FakeFrame(
            [
                {
                    "A股代码": "000001",
                    "A股简称": "平安银行",
                    "A股上市日期": "1991-04-03",
                }
            ]
        )

    def stock_info_sh_delist(self, symbol: str = "全部"):
        self.calls.append(("stock_info_sh_delist", {"symbol": symbol}))
        return FakeFrame([])

    def stock_info_sz_delist(self, symbol: str = "终止上市公司"):
        self.calls.append(("stock_info_sz_delist", {"symbol": symbol}))
        return FakeFrame(
            [
                {
                    "证券代码": "000005",
                    "证券简称": "ST星源",
                    "上市日期": "1990-12-10",
                    "终止上市日期": "2024-04-26",
                }
            ]
        )

    def stock_zh_a_hist_tx(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ):
        self.calls.append(
            (
                "stock_zh_a_hist_tx",
                {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "adjust": adjust,
                },
            )
        )
        return FakeFrame(
            [
                {
                    "date": "2024-08-26",
                    "open": 10.0,
                    "close": 10.2,
                    "high": 10.3,
                    "low": 9.9,
                    "volume": 123456,
                    "amount": 7890000.0,
                }
            ]
        )


class AkshareAdapterTest(unittest.TestCase):
    def test_stock_adapter_merges_active_and_delisted_lists(self) -> None:
        client = FakeAkshareClient()
        adapter = AkshareStockAdapter("stock_2026-09-03_001", client=client)

        records = adapter.fetch(FetchRequest(resource_type="stock", sync_mode="full"))

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].source_record_key, "SSE:600519")
        self.assertEqual(records[1].payload["_status"], "active")
        self.assertEqual(records[2].payload["_status"], "delisted")

    def test_trading_calendar_adapter_requires_date_range(self) -> None:
        client = FakeAkshareClient()
        adapter = AkshareTradingCalendarAdapter(
            "calendar_2026-09-03_001", client=client
        )

        with self.assertRaises(ConfigurationError):
            adapter.fetch(
                FetchRequest(
                    resource_type="trading_calendar",
                    sync_mode="full",
                    start_date="2026-01-01",
                )
            )

    def test_daily_quote_adapter_fetches_each_symbol_history(self) -> None:
        client = FakeAkshareClient()
        adapter = AkshareDailyQuoteAdapter(
            "daily_quote_2026-09-03_001",
            client=client,
            max_workers=1,
        )

        request = FetchRequest(
            resource_type="daily_quote",
            sync_mode="refresh",
            symbols=["600519", "000001"],
            start_date="2024-08-26",
            end_date="2024-08-26",
        )

        records = adapter.fetch(request)
        chunks = list(adapter.iter_fetch_chunks(request))

        self.assertEqual(len(records), 2)
        self.assertEqual(len(chunks), 2)
        self.assertEqual([len(chunk) for chunk in chunks], [1, 1])
        self.assertEqual(
            [
                call[1]["symbol"]
                for call in client.calls
                if call[0] == "stock_zh_a_hist_tx"
            ],
            ["sh600519", "sz000001", "sh600519", "sz000001"],
        )
        self.assertEqual(records[0].payload["_symbol"], "600519")
        self.assertEqual(chunks[1][0].payload["_symbol"], "000001")


if __name__ == "__main__":
    unittest.main()
