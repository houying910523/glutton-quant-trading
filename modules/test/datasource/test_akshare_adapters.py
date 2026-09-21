from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

from akshare.stock_feature import stock_hist_tx

from modules.datasource.adaptors.akshare import (
    AkshareDailyQuoteAdapter,
    AkshareStockAdapter,
    AkshareTradingCalendarAdapter,
    _disable_akshare_stock_hist_tx_tqdm,
)


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
        return FakeFrame(
            [
                {"trade_date": date(2024, 8, 26)},
                {"trade_date": date(2024, 8, 27)},
            ]
        )

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
                    "amount": 1259254.4,
                    "turnover": 7890000.0,
                }
            ]
        )


class DisableAkshareStockHistTxTqdmTest(unittest.TestCase):
    @patch(
        "modules.datasource.adaptors.akshare._AKSHARE_STOCK_HIST_TX_TQDM_DISABLED",
        False,
    )
    @patch.object(stock_hist_tx, "get_tqdm", return_value="original")
    def test_disable_akshare_stock_hist_tx_tqdm_replaces_progress_wrapper(
        self,
        _mock_get_tqdm,
    ) -> None:
        _disable_akshare_stock_hist_tx_tqdm()

        wrapped = stock_hist_tx.get_tqdm()
        self.assertEqual(list(wrapped([1, 2, 3])), [1, 2, 3])


class AkshareStockAdapterFetchTest(unittest.TestCase):
    def test_fetch_returns_active_and_delisted_records(self) -> None:
        client = FakeAkshareClient()
        adapter = AkshareStockAdapter()
        adapter._client = client

        records = adapter.fetch()

        self.assertEqual(
            {(record.exchange, record.symbol, record.status) for record in records},
            {
                ("SSE", "600519", "active"),
                ("SZSE", "000001", "active"),
                ("SZSE", "000005", "delisted"),
            },
        )


class AkshareTradingCalendarAdapterFetchTest(unittest.TestCase):
    def test_fetch_returns_open_dates(self) -> None:
        client = FakeAkshareClient()
        adapter = AkshareTradingCalendarAdapter()
        adapter._client = client

        records = adapter.fetch("2024-08-26", "2024-08-27")

        self.assertEqual(records, ["2024-08-26", "2024-08-27"])


class AkshareDailyQuoteAdapterFetchTest(unittest.TestCase):
    def test_fetch_returns_single_symbol_history(self) -> None:
        client = FakeAkshareClient()
        adapter = AkshareDailyQuoteAdapter()
        adapter._client = client

        records = adapter.fetch(
            symbol="600519",
            start_date="2024-08-26",
            end_date="2024-08-26",
            stock_id=1,
            batch_id=2,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(
            [call for call in client.calls if call[0] == "stock_zh_a_hist_tx"],
            [
                (
                    "stock_zh_a_hist_tx",
                    {
                        "symbol": "sh600519",
                        "start_date": "20240826",
                        "end_date": "20240826",
                        "adjust": "qfq",
                    },
                )
            ],
        )
        self.assertEqual(records[0].stock_id, 1)
        self.assertEqual(records[0].ingestion_batch_id, 2)
        self.assertEqual(records[0].open, 1000)
        self.assertEqual(records[0].close, 1020)


if __name__ == "__main__":
    unittest.main()
