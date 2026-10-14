from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.backtest.models import BacktestConfig, BacktestResult, EquityPoint
from modules.backtest.service import BacktestRunService
from modules.repositories.database import SQLiteDatabase
from modules.repositories.schema import SQLiteSchemaManager


def _initialize_database(root: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(root / "glutton.db")
    SQLiteSchemaManager(database).initialize()
    return database


class _FakeEngine:
    def run(self, strategy, config: BacktestConfig) -> BacktestResult:
        result = BacktestResult.empty(
            config=config,
            trade_dates=["2025-01-02"],
            rebalance_dates=["2025-01-02"],
        )
        result.equity_curve.append(
            EquityPoint(
                trade_date="2025-01-02",
                cash=float(config.initial_cash),
                market_value=0.0,
                total_equity=float(config.initial_cash),
            )
        )
        return result


class BacktestRunServiceTest(unittest.TestCase):
    def test_run_persists_successful_result_and_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = BacktestRunService(
                _initialize_database(Path(tmp_dir)),
                engine=_FakeEngine(),
            )

            record = service.run(
                strategy_id="buy_and_hold",
                strategy_params={"instrument_ids": ["000001.SZ"]},
                config={
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "initial_cash": 1000.0,
                    "rebalance_frequency": "monthly",
                },
            )

            self.assertEqual(record.status, "success")
            self.assertIsNotNone(record.started_at)
            self.assertIsNotNone(record.finished_at)
            self.assertIsNotNone(record.result_json)
            self.assertIsNotNone(record.analysis_json)
            assert record.result_json is not None
            assert record.analysis_json is not None
            self.assertEqual(record.result_json["summary"]["final_equity"], 1000.0)
            self.assertEqual(record.analysis_json["metadata"]["equity_points"], 1)

            detail = service.get(record.id or 0)
            recent = service.list_recent(limit=5)

            self.assertIsNotNone(detail)
            self.assertEqual(recent[0]["id"], record.id)
            self.assertEqual(recent[0]["summary"]["final_equity"], 1000.0)

    def test_run_persists_failed_record_when_strategy_id_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = BacktestRunService(_initialize_database(Path(tmp_dir)))

            record = service.run(
                strategy_id="unknown_strategy",
                strategy_params={},
                config={
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                },
            )

            self.assertEqual(record.status, "failed")
            self.assertEqual(
                record.error_summary,
                "unsupported strategy_id: unknown_strategy",
            )
            self.assertIsNotNone(record.started_at)
            self.assertIsNotNone(record.finished_at)

    def test_run_persists_failed_record_when_strategy_params_are_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = BacktestRunService(_initialize_database(Path(tmp_dir)))

            record = service.run(
                strategy_id="buy_and_hold",
                strategy_params={"instrument_ids": "000001.SZ"},
                config={
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                },
            )

            self.assertEqual(record.status, "failed")
            self.assertEqual(record.error_summary, "instrument_ids must be a list")


if __name__ == "__main__":
    unittest.main()
