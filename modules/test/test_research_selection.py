from datetime import date, datetime, timedelta
import unittest
from unittest.mock import patch

try:
    import polars as pl
except ModuleNotFoundError:  # pragma: no cover - optional at test runtime
    pl = None


@unittest.skipIf(pl is None, "polars is not installed")
class SelectionGroupStockDailyDataTest(unittest.TestCase):
    def test_group_stock_daily_data_groups_by_instrument_id(self) -> None:
        from modules.research.selection import Selection

        data = pl.DataFrame(
            {
                "trade_date": ["2024-01-02", "2024-01-01", "2024-01-01"],
                "instrument_id": ["000001.SZ", "600519.SH", "000001.SZ"],
                "close": [10.5, 20.5, 10.0],
            }
        ).with_columns(pl.col("trade_date").str.strptime(pl.Date, "%Y-%m-%d"))

        grouped_data = Selection._group_stock_daily_data(data)

        self.assertEqual(
            [item.instrument_id for item in grouped_data],
            ["000001.SZ", "600519.SH"],
        )
        self.assertEqual(
            grouped_data[0].data["trade_date"].to_list(),
            [date(2024, 1, 1), date(2024, 1, 2)],
        )
        self.assertEqual(
            grouped_data[0].data["close"].to_list(),
            [10.0, 10.5],
        )
        self.assertEqual(grouped_data[1].data["close"].to_list(), [20.5])


@unittest.skipIf(pl is None, "polars is not installed")
class SelectionRunTest(unittest.TestCase):
    from modules.research import selection as selection_module

    @patch.object(selection_module, "StockDailyService")
    @patch.object(selection_module, "now_shanghai")
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

        selection = Selection(database=object())
        selection.run(filters=[])

        mock_stock_daily_service.return_value.load_stock_daily.assert_called_once_with(
            start_date=date(2024, 4, 30) - timedelta(days=LOOKBACK_DAYS),
            end_date=date(2024, 4, 30),
            optional=False,
        )
