import unittest

from modules.test.filters.common import _build_stock_daily_data


class MainBoardFilterTest(unittest.TestCase):
    def test_filter_keeps_only_sse_and_szse_main_board_stocks(self) -> None:
        from modules.filters.main_board import MainBoardFilter

        main_board_sse = _build_stock_daily_data(
            "600519.SH",
            closes=[10.0, 10.1, 10.2],
        )
        main_board_szse = _build_stock_daily_data(
            "000001.SZ",
            closes=[20.0, 20.1, 20.2],
        )
        chi_next = _build_stock_daily_data(
            "300750.SZ",
            closes=[30.0, 30.1, 30.2],
        )
        star_market = _build_stock_daily_data(
            "688981.SH",
            closes=[40.0, 40.1, 40.2],
        )

        result = MainBoardFilter().filter(
            [main_board_sse, main_board_szse, chi_next, star_market]
        )

        self.assertEqual(
            [item.instrument_id for item in result],
            ["600519.SH", "000001.SZ"],
        )

    def test_filter_rejects_unknown_or_malformed_instrument_ids(self) -> None:
        from modules.filters.main_board import MainBoardFilter

        candidates = [
            _build_stock_daily_data("430001.BJ", closes=[10.0, 10.1, 10.2]),
            _build_stock_daily_data("ABC123.SZ", closes=[11.0, 11.1, 11.2]),
            _build_stock_daily_data("600519", closes=[12.0, 12.1, 12.2]),
        ]

        result = MainBoardFilter().filter(candidates)

        self.assertEqual(result, [])
