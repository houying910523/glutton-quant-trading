from datetime import date
import unittest

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
