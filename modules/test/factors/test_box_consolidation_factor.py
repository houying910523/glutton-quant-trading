from __future__ import annotations

import unittest
from datetime import date, timedelta

import polars as pl

from modules.core.context import Context, StockDailyData
from modules.factors.box_consolidation import BoxConsolidationMatchFactor


def _build_stock_daily_data(
    instrument_id: str,
    *,
    closes: list[float],
) -> StockDailyData:
    assert pl is not None

    trade_dates = [
        date(2024, 1, 1) + timedelta(days=index) for index in range(len(closes))
    ]
    return StockDailyData(
        instrument_id=instrument_id,
        data=pl.DataFrame(
            {
                "trade_date": trade_dates,
                "close": closes,
            }
        ),
    )


class BoxConsolidationDiagnosticsTest(unittest.TestCase):
    def test_evaluate_closes_matches_flat_box_pattern(self) -> None:
        closes = [
            100.0,
            103.0,
            106.0,
            109.0,
            112.0,
            109.0,
            106.0,
            103.0,
            100.0,
            97.0,
            94.0,
            97.0,
        ] * 3 + [100.0, 103.0, 106.0, 109.0, 112.0, 109.0, 106.0, 103.0]

        result = BoxConsolidationMatchFactor.evaluate_closes(closes)

        self.assertTrue(result.matched)
        self.assertIsNone(result.first_failure_reason)
        self.assertEqual(result.details["peak_count"], 4)
        self.assertEqual(result.details["valley_count"], 3)

    def test_evaluate_closes_reports_upper_drift_as_first_failure(self) -> None:
        base_pattern = [0.0, 3.0, 6.0, 9.0, 12.0, 9.0, 6.0, 3.0, 0.0, -3.0, -6.0, -3.0]
        closes = [
            100.0 + base_pattern[index % len(base_pattern)] + 0.30 * index
            for index in range(44)
        ]

        result = BoxConsolidationMatchFactor.evaluate_closes(closes)

        self.assertFalse(result.matched)
        self.assertEqual(
            result.first_failure_reason,
            "upper_boundary_drift_too_large",
        )
        self.assertFalse(result.condition_results["upper_boundary_drift"])

    def test_evaluate_closes_reports_recent_prices_outside_box(self) -> None:
        closes = (
            [
                100.0,
                103.0,
                106.0,
                109.0,
                112.0,
                109.0,
                106.0,
                103.0,
                100.0,
                97.0,
                94.0,
                97.0,
            ]
            * 3
            + [100.0, 103.0, 106.0, 109.0, 112.0]
            + [116.0, 118.0, 120.0]
        )

        result = BoxConsolidationMatchFactor.evaluate_closes(closes)

        self.assertFalse(result.matched)
        self.assertEqual(
            result.first_failure_reason,
            "recent_prices_outside_box",
        )
        self.assertEqual(result.details["recent_inside_count"], 0)
        self.assertFalse(result.details["latest_inside"])


@unittest.skipIf(pl is None, "polars is not installed")
class BoxConsolidationCreateFilterIntegrationTest(unittest.TestCase):
    def test_create_filter_loads_box_consolidation_filter(self) -> None:
        from modules.filters import create_filter
        from modules.filters.box_consolidation import BoxConsolidationFilter

        filter_instance = create_filter("box_consolidation")

        self.assertIsInstance(filter_instance, BoxConsolidationFilter)


@unittest.skipIf(pl is None, "polars is not installed")
class BoxConsolidationMatchFactorTest(unittest.TestCase):
    def test_compute_returns_factor_frame_for_each_stock(self) -> None:
        matched_stock = _build_stock_daily_data(
            "000001.SZ",
            closes=[
                100.0,
                103.0,
                106.0,
                109.0,
                112.0,
                109.0,
                106.0,
                103.0,
                100.0,
                97.0,
                94.0,
                97.0,
            ]
            * 3
            + [100.0, 103.0, 106.0, 109.0, 112.0, 109.0, 106.0, 103.0],
        )
        unmatched_stock = _build_stock_daily_data(
            "600519.SH",
            closes=[80.0 + 1.2 * index for index in range(44)],
        )
        factor = BoxConsolidationMatchFactor()

        result = factor.compute(
            Context(
                start_date="2024-01-01",
                end_date="2024-02-29",
                stock_daily_data=[matched_stock, unmatched_stock],
            )
        )

        self.assertEqual(
            sorted(result.keys()),
            ["000001.SZ", "600519.SH"],
        )
        matched_frame = result["000001.SZ"]
        unmatched_frame = result["600519.SH"]

        self.assertEqual(
            matched_frame.columns,
            ["instrument_id", "trade_date", "factor_value"],
        )
        self.assertEqual(matched_frame.height, 44)
        self.assertEqual(unmatched_frame.height, 44)
        self.assertEqual(
            matched_frame.get_column("trade_date").to_list()[-1],
            date(2024, 2, 13),
        )
        self.assertEqual(
            unmatched_frame.get_column("trade_date").to_list()[-1],
            date(2024, 2, 13),
        )
        self.assertTrue(matched_frame.get_column("factor_value").to_list()[-1])
        self.assertFalse(unmatched_frame.get_column("factor_value").to_list()[-1])
        self.assertEqual(
            matched_frame.get_column("instrument_id").unique().to_list(),
            ["000001.SZ"],
        )

    def test_compute_returns_false_when_history_is_insufficient(self) -> None:
        stock_daily_data = _build_stock_daily_data(
            "000002.SZ",
            closes=[10.0, 10.5, 10.2, 10.4] * 5,
        )
        factor = BoxConsolidationMatchFactor()

        result = factor.compute(
            Context(
                start_date="2024-01-01",
                end_date="2024-01-20",
                stock_daily_data=[stock_daily_data],
            )
        )

        factor_frame = result["000002.SZ"]
        self.assertEqual(factor_frame.height, 20)
        self.assertEqual(
            factor_frame.get_column("factor_value").to_list(),
            [False] * 20,
        )


@unittest.skipIf(pl is None, "polars is not installed")
class BoxConsolidationFilterDelegationTest(unittest.TestCase):
    def test_filter_keeps_only_stocks_matched_by_factor_logic(self) -> None:
        from modules.filters.box_consolidation import BoxConsolidationFilter

        matched_stock = _build_stock_daily_data(
            "000003.SZ",
            closes=[
                100.0,
                103.0,
                106.0,
                109.0,
                112.0,
                109.0,
                106.0,
                103.0,
                100.0,
                97.0,
                94.0,
                97.0,
            ]
            * 3
            + [100.0, 103.0, 106.0, 109.0, 112.0, 109.0, 106.0, 103.0],
        )
        unmatched_stock = _build_stock_daily_data(
            "000004.SZ",
            closes=[80.0 + 1.2 * index for index in range(44)],
        )

        result = BoxConsolidationFilter().filter([matched_stock, unmatched_stock])

        self.assertEqual([item.instrument_id for item in result], ["000003.SZ"])

    def test_filter_rejects_boundaries_when_drift_exceeds_threshold(self) -> None:
        from modules.filters.box_consolidation import BoxConsolidationFilter

        drifting = _build_stock_daily_data(
            "000006.SZ",
            closes=[
                100.0
                + [0.0, 3.0, 6.0, 9.0, 12.0, 9.0, 6.0, 3.0, 0.0, -3.0, -6.0, -3.0][
                    index % 12
                ]
                + 0.30 * index
                for index in range(44)
            ],
        )

        result = BoxConsolidationFilter().filter([drifting])

        self.assertEqual(result, [])

    def test_filter_rejects_stock_when_recent_prices_leave_box(self) -> None:
        from modules.filters.box_consolidation import BoxConsolidationFilter

        stock_daily_data = _build_stock_daily_data(
            "000007.SZ",
            closes=(
                [
                    100.0,
                    103.0,
                    106.0,
                    109.0,
                    112.0,
                    109.0,
                    106.0,
                    103.0,
                    100.0,
                    97.0,
                    94.0,
                    97.0,
                ]
                * 3
                + [100.0, 103.0, 106.0, 109.0, 112.0]
                + [116.0, 118.0, 120.0]
            ),
        )

        result = BoxConsolidationFilter().filter([stock_daily_data])

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
