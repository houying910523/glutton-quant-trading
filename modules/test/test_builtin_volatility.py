from __future__ import annotations

import unittest
from datetime import date

try:
    import polars as pl
    from modules.indicators.builtin.volatility import AverageTrueRangeIndicator
except ModuleNotFoundError:  # pragma: no cover - optional at test runtime
    pl = None
    AverageTrueRangeIndicator = None


@unittest.skipIf(pl is None, "polars is not installed")
class AverageTrueRangeIndicatorSpecTest(unittest.TestCase):
    def test_spec_returns_expected_required_columns_and_output(self) -> None:
        indicator = AverageTrueRangeIndicator()

        spec = indicator.spec({"window": 14})

        self.assertEqual(spec.required_columns, ["high", "low", "close"])
        self.assertEqual(spec.required_history_bars, 28)
        self.assertEqual(spec.output_columns, ["atr_14"])


@unittest.skipIf(pl is None, "polars is not installed")
class AverageTrueRangeIndicatorComputeTest(unittest.TestCase):
    def test_compute_returns_expected_atr_series(self) -> None:
        indicator = AverageTrueRangeIndicator()
        frame = pl.DataFrame(
            {
                "trade_date": [
                    date(2024, 1, 3),
                    date(2024, 1, 1),
                    date(2024, 1, 5),
                    date(2024, 1, 2),
                    date(2024, 1, 4),
                ],
                "instrument_id": ["600519.SH"] * 5,
                "high": [13.0, 10.0, 14.0, 12.0, 15.0],
                "low": [11.0, 8.0, 10.0, 9.0, 12.0],
                "close": [12.0, 9.0, 11.0, 11.0, 13.0],
            }
        )

        result = indicator.compute(frame, {"window": 3})

        self.assertEqual(
            result["trade_date"].to_list(),
            [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 5),
            ],
        )
        self.assertEqual(result["instrument_id"].to_list(), ["600519.SH"] * 5)

        atr_values = result["atr_3"].to_list()
        self.assertEqual(atr_values[:2], [None, None])
        self.assertAlmostEqual(atr_values[2], 7.0 / 3.0, places=8)
        self.assertAlmostEqual(atr_values[3], 23.0 / 9.0, places=8)
        self.assertAlmostEqual(atr_values[4], 82.0 / 27.0, places=8)


if __name__ == "__main__":
    unittest.main()
