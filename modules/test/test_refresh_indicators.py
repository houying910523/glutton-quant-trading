from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import polars as pl
except ModuleNotFoundError:  # pragma: no cover - optional at test runtime
    pl = None

from modules.indicators.models import IndicatorDefinition, IndicatorSpec


@unittest.skipIf(pl is None, "polars is not installed")
class ResolveEffectiveStartDateTest(unittest.TestCase):
    def test_resolve_effective_start_date_returns_start_when_no_progress(self) -> None:
        from modules.indicators.scripts.refresh_indicators import (
            _resolve_effective_start_date,
        )

        resolved = _resolve_effective_start_date(
            self._make_indicator_definition(last_materialized_date=None),
            date(2024, 1, 1),
            date(2024, 2, 10),
            force=False,
        )

        self.assertEqual(resolved, date(2024, 1, 1))

    def test_resolve_effective_start_date_resumes_from_last_materialized_date(
        self,
    ) -> None:
        from modules.indicators.scripts.refresh_indicators import (
            _resolve_effective_start_date,
        )

        resolved = _resolve_effective_start_date(
            self._make_indicator_definition(last_materialized_date="2024-01-25"),
            date(2024, 1, 1),
            date(2024, 2, 10),
            force=False,
        )

        self.assertEqual(resolved, date(2024, 1, 25))

    def test_resolve_effective_start_date_force_ignores_existing_progress(self) -> None:
        from modules.indicators.scripts.refresh_indicators import (
            _resolve_effective_start_date,
        )

        resolved = _resolve_effective_start_date(
            self._make_indicator_definition(last_materialized_date="2024-01-25"),
            date(2024, 1, 1),
            date(2024, 2, 10),
            force=True,
        )

        self.assertEqual(resolved, date(2024, 1, 1))

    @classmethod
    def _make_indicator_definition(
        cls, *, last_materialized_date: str | None
    ) -> IndicatorDefinition:
        return IndicatorDefinition(
            indicator_id="ma_20",
            version="v1",
            indicator_name="20日均线",
            category="trend",
            compute_ref="modules.indicators.builtin.trend:SimpleMovingAverageIndicator",
            params={"window": [20]},
            output_columns=["ma_20"],
            storage_key="ma/v1/window_20",
            description=None,
            status="active",
            last_materialized_date=last_materialized_date,
        )


@unittest.skipIf(pl is None, "polars is not installed")
class PendingYearRangesTest(unittest.TestCase):
    def test_pending_year_ranges_returns_full_years_without_progress(self) -> None:
        from modules.indicators.scripts.refresh_indicators import _pending_year_ranges

        ranges = _pending_year_ranges(
            self._make_indicator_definition(last_materialized_date=None),
            date(2024, 1, 1),
            date(2025, 2, 10),
        )

        self.assertEqual(
            ranges,
            [
                (date(2024, 1, 1), date(2024, 1, 1), date(2024, 12, 31)),
                (date(2025, 1, 1), date(2025, 1, 1), date(2025, 2, 10)),
            ],
        )

    def test_pending_year_ranges_resumes_from_next_year(self) -> None:
        from modules.indicators.scripts.refresh_indicators import _pending_year_ranges

        ranges = _pending_year_ranges(
            self._make_indicator_definition(last_materialized_date="2024-12-31"),
            date(2024, 1, 1),
            date(2025, 2, 10),
        )

        self.assertEqual(
            ranges,
            [(date(2025, 1, 1), date(2025, 1, 1), date(2025, 2, 10))],
        )

    def test_pending_year_ranges_resumes_within_existing_year(self) -> None:
        from modules.indicators.scripts.refresh_indicators import _pending_year_ranges

        ranges = _pending_year_ranges(
            self._make_indicator_definition(last_materialized_date="2024-01-24"),
            date(2024, 1, 1),
            date(2025, 2, 10),
        )

        self.assertEqual(
            ranges,
            [
                (date(2024, 1, 1), date(2024, 1, 25), date(2024, 12, 31)),
                (date(2025, 1, 1), date(2025, 1, 1), date(2025, 2, 10)),
            ],
        )

    @classmethod
    def _make_indicator_definition(
        cls, *, last_materialized_date: str | None
    ) -> IndicatorDefinition:
        return IndicatorDefinition(
            indicator_id="ma_20",
            version="v1",
            indicator_name="20日均线",
            category="trend",
            compute_ref="modules.indicators.builtin.trend:SimpleMovingAverageIndicator",
            params={"window": [20]},
            output_columns=["ma_20"],
            storage_key="ma/v1/window_20",
            description=None,
            status="active",
            last_materialized_date=last_materialized_date,
        )


@unittest.skipIf(pl is None, "polars is not installed")
class RefreshIndicatorTest(unittest.TestCase):
    @patch("modules.indicators.scripts.refresh_indicators.load_indicator")
    def test_refresh_indicator_writes_filtered_rows(self, mock_load_indicator) -> None:
        from modules.indicators.scripts.refresh_indicators import refresh_indicator

        indicator_definition = self._make_indicator_definition(
            last_materialized_date=None
        )
        loader = MagicMock()
        loader.load_stock_daily.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 1), date(2024, 1, 2)],
                "instrument_id": ["600519.SH", "600519.SH"],
                "close": [10.0, 11.0],
            }
        )
        store = MagicMock()
        store.write_year_partition.return_value = Path("/tmp/ma-2024.parquet")
        indicator = MagicMock()
        indicator.spec.return_value = IndicatorSpec(
            required_columns=["close"],
            required_history_bars=0,
            output_columns=["ma_20"],
        )
        indicator.compute.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 1), date(2024, 1, 2)],
                "instrument_id": ["600519.SH", "600519.SH"],
                "ma_20": [10.0, 10.5],
                "ignored": ["x", "y"],
            }
        )
        mock_load_indicator.return_value = indicator
        materialized_dates: list[date] = []

        result = refresh_indicator(
            indicator_definition,
            loader,
            store,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            instruments=["600519.SH"],
            on_year_materialized=materialized_dates.append,
        )

        loader.load_stock_daily.assert_called_once_with(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            instruments=["600519.SH"],
            columns=["close"],
        )
        written_frame = store.write_year_partition.call_args.kwargs["frame"]
        self.assertEqual(
            written_frame.columns, ["trade_date", "instrument_id", "ma_20"]
        )
        self.assertEqual(written_frame.height, 2)
        self.assertEqual(result["rows_written"], 2)
        self.assertEqual(result["last_materialized_date"], "2024-01-02")
        self.assertEqual(materialized_dates, [date(2024, 1, 2)])

    @patch(
        "modules.indicators.scripts.refresh_indicators._read_existing_year_partition"
    )
    @patch("modules.indicators.scripts.refresh_indicators.load_indicator")
    def test_refresh_indicator_merges_existing_partition_when_resuming(
        self,
        mock_load_indicator,
        mock_read_existing_year_partition,
    ) -> None:
        from modules.indicators.scripts.refresh_indicators import refresh_indicator

        indicator_definition = self._make_indicator_definition(
            last_materialized_date="2024-01-24"
        )
        loader = MagicMock()
        loader.load_stock_daily.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 25)],
                "instrument_id": ["600519.SH"],
                "close": [12.0],
            }
        )
        store = MagicMock()
        store.write_year_partition.return_value = Path("/tmp/ma-2024.parquet")
        indicator = MagicMock()
        indicator.spec.return_value = IndicatorSpec(
            required_columns=["close"],
            required_history_bars=0,
            output_columns=["ma_20"],
        )
        indicator.compute.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 25)],
                "instrument_id": ["600519.SH"],
                "ma_20": [12.0],
            }
        )
        mock_load_indicator.return_value = indicator
        mock_read_existing_year_partition.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 24)],
                "instrument_id": ["600519.SH"],
                "ma_20": [11.5],
            }
        )

        refresh_indicator(
            indicator_definition,
            loader,
            store,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        written_frame = store.write_year_partition.call_args.kwargs["frame"]
        self.assertEqual(written_frame.height, 2)
        self.assertEqual(
            written_frame["trade_date"].to_list(),
            [date(2024, 1, 24), date(2024, 1, 25)],
        )

    @classmethod
    def _make_indicator_definition(
        cls, *, last_materialized_date: str | None
    ) -> IndicatorDefinition:
        return IndicatorDefinition(
            indicator_id="ma_20",
            version="v1",
            indicator_name="20日均线",
            category="trend",
            compute_ref="modules.indicators.builtin.trend:SimpleMovingAverageIndicator",
            params={"window": [20]},
            output_columns=["ma_20"],
            storage_key="ma/v1/window_20",
            description=None,
            status="active",
            last_materialized_date=last_materialized_date,
        )


@unittest.skipIf(pl is None, "polars is not installed")
class RefreshIndicatorsTest(unittest.TestCase):
    @patch("modules.indicators.scripts.refresh_indicators.tqdm")
    @patch("modules.indicators.scripts.refresh_indicators.refresh_indicator")
    @patch("modules.indicators.scripts.refresh_indicators._pending_year_ranges")
    @patch(
        "modules.indicators.scripts.refresh_indicators._resolve_effective_start_date"
    )
    @patch("modules.indicators.scripts.refresh_indicators._load_indicator_definitions")
    @patch("modules.indicators.scripts.refresh_indicators.RepositorySession")
    @patch("modules.indicators.scripts.refresh_indicators.IndicatorStore")
    @patch("modules.indicators.scripts.refresh_indicators.StockDailyService")
    @patch("modules.indicators.scripts.refresh_indicators.SQLiteSchemaManager")
    def test_refresh_indicators_persists_yearly_progress_before_later_failure(
        self,
        mock_schema_manager,
        mock_stock_daily_service,
        mock_indicator_store,
        mock_repository_session,
        mock_load_indicator_definitions,
        mock_resolve_effective_start_date,
        mock_pending_year_ranges,
        mock_refresh_indicator,
        mock_tqdm,
    ) -> None:
        from modules.indicators.scripts.refresh_indicators import refresh_indicators

        indicator_definition = IndicatorDefinition(
            indicator_id="ma_20",
            version="v1",
            indicator_name="20日均线",
            category="trend",
            compute_ref="modules.indicators.builtin.trend:SimpleMovingAverageIndicator",
            params={"window": [20]},
            output_columns=["ma_20"],
            storage_key="ma/v1/window_20",
            description=None,
            status="active",
            last_materialized_date=None,
        )
        definition_session = MagicMock()
        definition_session.__enter__.return_value = definition_session
        definition_session.__exit__.return_value = None
        update_session = MagicMock()
        update_session.__enter__.return_value = update_session
        update_session.__exit__.return_value = None
        mock_repository_session.side_effect = [definition_session, update_session]
        mock_load_indicator_definitions.return_value = [indicator_definition]
        mock_resolve_effective_start_date.return_value = date(2024, 1, 1)
        mock_pending_year_ranges.return_value = [
            (date(2024, 1, 1), date(2024, 1, 1), date(2024, 12, 31)),
            (date(2025, 1, 1), date(2025, 1, 1), date(2025, 2, 10)),
        ]
        progress = MagicMock()
        mock_tqdm.return_value = progress

        def raise_after_first_materialized(*args, **kwargs):
            kwargs["on_year_materialized"](date(2024, 12, 31))
            raise RuntimeError("simulated failure")

        mock_refresh_indicator.side_effect = raise_after_first_materialized

        with self.assertRaisesRegex(RuntimeError, "simulated failure"):
            refresh_indicators(
                MagicMock(),
                Path("/tmp/research/factors"),
                indicator_ids=["ma_20"],
                start_date=date(2024, 1, 1),
                end_date=date(2025, 2, 10),
                instruments=["600519.SH"],
            )

        mock_schema_manager.return_value.initialize.assert_called_once_with()
        mock_stock_daily_service.assert_called_once()
        mock_indicator_store.assert_called_once()
        update_session.indicator.set_last_materialized_date.assert_called_once_with(
            indicator_id="ma_20",
            version="v1",
            last_materialized_date="2024-12-31",
        )
        progress.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
