from __future__ import annotations

from datetime import date, datetime, timedelta
import unittest
from unittest.mock import patch

try:
    import polars as pl
except ModuleNotFoundError:  # pragma: no cover - optional at test runtime
    pl = None

from modules.core.context import StockDailyData


def _build_stock_daily_data(
    instrument_id: str,
    *,
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    turnover_rates: list[float] | None = None,
) -> StockDailyData:
    assert pl is not None

    if highs is None:
        highs = [value + 1.0 for value in closes]
    if lows is None:
        lows = [value - 1.0 for value in closes]
    if turnover_rates is None:
        turnover_rates = [1.0] * len(closes)

    trade_dates = [
        date(2024, 1, 1) + timedelta(days=index) for index in range(len(closes))
    ]
    return StockDailyData(
        instrument_id=instrument_id,
        data=pl.DataFrame(
            {
                "trade_date": trade_dates,
                "close": closes,
                "high": highs,
                "low": lows,
                "turnover": turnover_rates,
            }
        ),
    )


@unittest.skipIf(pl is None, "polars is not installed")
class CreateFilterIntegrationTest(unittest.TestCase):
    def test_create_filter_loads_box_oscillation_gain_filter(self) -> None:
        from modules.filters import create_filter
        from modules.filters.box_oscillation_gain import BoxOscillationGainFilter

        filter_instance = create_filter("box_oscillation_gain")

        self.assertIsInstance(filter_instance, BoxOscillationGainFilter)

    def test_create_filter_loads_main_board_filter(self) -> None:
        from modules.filters import create_filter
        from modules.filters.main_board import MainBoardFilter

        filter_instance = create_filter("main_board")

        self.assertIsInstance(filter_instance, MainBoardFilter)

    def test_create_filter_loads_three_day_turnover_rate_filter(self) -> None:
        from modules.filters import create_filter
        from modules.filters.turnover import TurnoverFilter

        filter_instance = create_filter("turnover")

        self.assertIsInstance(filter_instance, TurnoverFilter)


@unittest.skipIf(pl is None, "polars is not installed")
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


@unittest.skipIf(pl is None, "polars is not installed")
class BoxOscillationGainFilterFilterTest(unittest.TestCase):
    def test_filter_keeps_stock_in_horizontal_box_with_recent_prices_inside(
        self,
    ) -> None:
        from modules.filters.box_oscillation_gain import BoxOscillationGainFilter

        in_box = _build_stock_daily_data(
            "000001.SZ",
            closes=[100.0, 104.0, 99.0, 103.0, 98.0, 102.0] * 10,
        )
        trending = _build_stock_daily_data(
            "600519.SH",
            closes=[100.0, 112.0, 95.0, 128.0, 90.0, 140.0] * 10,
        )

        result = BoxOscillationGainFilter().filter([in_box, trending])

        self.assertEqual([item.instrument_id for item in result], ["000001.SZ"])

    def test_filter_rejects_stock_when_recent_prices_leave_box(self) -> None:
        from modules.filters.box_oscillation_gain import BoxOscillationGainFilter

        closes = ([100.0, 104.0, 99.0, 103.0, 98.0, 102.0] * 9) + [
            106.0,
            107.0,
            106.0,
            107.0,
            108.0,
            109.0,
        ]
        stock_daily_data = _build_stock_daily_data("000002.SZ", closes=closes)

        result = BoxOscillationGainFilter().filter([stock_daily_data])

        self.assertEqual(result, [])

    def test_filter_rejects_rising_channel_without_horizontal_boundaries(self) -> None:
        from modules.filters.box_oscillation_gain import BoxOscillationGainFilter

        closes: list[float] = []
        for step in range(10):
            base = 100.0 + step * 1.5
            closes.extend([base, base + 4.0, base + 1.0, base + 3.0, base, base + 2.0])

        stock_daily_data = _build_stock_daily_data("000003.SZ", closes=closes)

        result = BoxOscillationGainFilter().filter([stock_daily_data])

        self.assertEqual(result, [])

    def test_filter_rejects_box_with_too_small_height(self) -> None:
        from modules.filters.box_oscillation_gain import BoxOscillationGainFilter

        stock_daily_data = _build_stock_daily_data(
            "000004.SZ",
            closes=[100.0, 101.0, 100.2, 100.8, 100.1, 100.9] * 10,
        )

        result = BoxOscillationGainFilter().filter([stock_daily_data])

        self.assertEqual(result, [])

    def test_collect_extrema_points_skips_same_day_dual_extrema(self) -> None:
        from modules.filters.box_oscillation_gain import BoxOscillationGainFilter

        result = BoxOscillationGainFilter._collect_extrema_points(
            [10.0, 20.0, 10.0],
            [10.0, 1.0, 10.0],
        )

        self.assertEqual(result, [])

    def test_filter_requires_price_to_switch_between_upper_and_lower_zones(
        self,
    ) -> None:
        from modules.filters.box_oscillation_gain import (
            BoundaryZone,
            BoxOscillationGainFilter,
        )

        upper_zone = BoundaryZone(
            lower=109.0,
            upper=111.0,
            center=110.0,
            points=[(5, 110.0), (20, 109.5)],
        )
        lower_zone = BoundaryZone(
            lower=99.0,
            upper=101.0,
            center=100.0,
            points=[(10, 100.0), (25, 99.5)],
        )

        self.assertFalse(
            BoxOscillationGainFilter._has_oscillation_between_zones(
                [
                    (5, "upper", 110.0),
                    (10, "upper", 109.5),
                    (20, "lower", 100.0),
                    (25, "lower", 99.5),
                ],
                upper_zone,
                lower_zone,
            )
        )

        self.assertTrue(
            BoxOscillationGainFilter._has_oscillation_between_zones(
                [
                    (5, "upper", 110.0),
                    (10, "lower", 100.0),
                    (20, "upper", 109.5),
                    (25, "lower", 99.5),
                ],
                upper_zone,
                lower_zone,
            )
        )


@unittest.skipIf(pl is None, "polars is not installed")
class ThreeDayTurnoverRateFilterFilterTest(unittest.TestCase):
    def test_filter_keeps_stock_with_last_three_turnover_rates_above_five(self) -> None:
        from modules.filters.turnover import TurnoverFilter

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

        result = TurnoverFilter().filter([matched, rejected])

        self.assertEqual([item.instrument_id for item in result], ["000001.SZ"])


@unittest.skipIf(pl is None, "polars is not installed")
class SelectionRunTest(unittest.TestCase):
    @patch("modules.research.selection.StockDailyService")
    @patch("modules.research.selection.now_shanghai")
    def test_run_loads_enough_history_for_sixty_day_filters(
        self,
        mock_now_shanghai,
        mock_stock_daily_service,
    ) -> None:
        from modules.research.selection import LOOKBACK_DAYS, Selection

        mock_now_shanghai.return_value = datetime(2024, 4, 30, 15, 0, 0)
        mock_stock_daily_service.return_value.load_stock_daily.return_value = (
            pl.DataFrame(
                schema={
                    "trade_date": pl.Date,
                    "instrument_id": pl.Utf8,
                    "open": pl.Float64,
                    "high": pl.Float64,
                    "low": pl.Float64,
                    "close": pl.Float64,
                    "volume": pl.Int64,
                    "turnover": pl.Float64,
                }
            )
        )

        selection = Selection(database=object(), filters=[])
        selection.run()

        mock_stock_daily_service.return_value.load_stock_daily.assert_called_once_with(
            start_date=date(2024, 4, 30) - timedelta(days=LOOKBACK_DAYS),
            end_date=date(2024, 4, 30),
        )


if __name__ == "__main__":
    unittest.main()
