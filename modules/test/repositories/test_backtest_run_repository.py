from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.schema import SQLiteSchemaManager


def _initialize_database(root: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(root / "glutton.db")
    SQLiteSchemaManager(database).initialize()
    return database


class BacktestRunRepositoryTest(unittest.TestCase):
    def test_create_and_complete_success_persists_result_and_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database = _initialize_database(Path(tmp_dir))

            with RepositorySession(database, transactional=True) as repositories:
                created = repositories.backtest_run.create(
                    strategy_id="buy_and_hold",
                    strategy_params={"instrument_ids": ["000001.SZ"]},
                    config={
                        "start_date": "2025-01-01",
                        "end_date": "2025-12-31",
                    },
                )
                assert created.id is not None
                repositories.backtest_run.mark_running(created.id)
                persisted = repositories.backtest_run.complete_success(
                    run_id=created.id,
                    result_json={"summary": {"final_equity": 101.0}},
                    analysis_json={"summary": {"total_return": 0.01}},
                )

            self.assertEqual(persisted.status, "success")
            self.assertIsNotNone(persisted.started_at)
            self.assertIsNotNone(persisted.finished_at)

            with RepositorySession(database) as repositories:
                fetched = repositories.backtest_run.get(created.id)
                recent = repositories.backtest_run.list_recent(limit=10)

            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.strategy_id, "buy_and_hold")
            self.assertEqual(fetched.result_json, {"summary": {"final_equity": 101.0}})
            self.assertEqual(fetched.analysis_json, {"summary": {"total_return": 0.01}})
            self.assertEqual([item.id for item in recent], [created.id])

    def test_complete_failure_persists_error_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database = _initialize_database(Path(tmp_dir))

            with RepositorySession(database, transactional=True) as repositories:
                created = repositories.backtest_run.create(
                    strategy_id="unknown",
                    strategy_params={},
                    config={
                        "start_date": "2025-01-01",
                        "end_date": "2025-12-31",
                    },
                )
                assert created.id is not None
                repositories.backtest_run.mark_running(created.id)
                failed = repositories.backtest_run.complete_failure(
                    run_id=created.id,
                    error_summary="unsupported strategy_id: unknown",
                )

            self.assertEqual(failed.status, "failed")
            self.assertEqual(
                failed.error_summary,
                "unsupported strategy_id: unknown",
            )
            self.assertIsNotNone(failed.finished_at)


if __name__ == "__main__":
    unittest.main()
