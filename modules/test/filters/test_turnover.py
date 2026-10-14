import unittest

from modules.test.filters.common import _build_stock_daily_data


class TurnoverFilterTest(unittest.TestCase):
    def test_filter_keeps_stock_with_last_three_turnover_rates_above_five(self) -> None:
        from modules.filters.turnover_rate import TurnoverRateFilter

        matched = _build_stock_daily_data(
            "000001.SZ",
            closes=[10.0, 10.1, 10.2, 10.3],
            turnover_rates=[4.2, 5.01, 5.55, 6.12],
        )
        rejected = _build_stock_daily_data(
            "600519.SH",
            closes=[20.0, 20.1, 20.2, 20.3],
            turnover_rates=[6.2, 0.04, 6.1, 6.3],
        )

        result = TurnoverRateFilter().filter([matched, rejected])

        self.assertEqual([item.instrument_id for item in result], ["000001.SZ"])
