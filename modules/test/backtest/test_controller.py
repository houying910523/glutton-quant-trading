from __future__ import annotations

import unittest

from modules.controller.backtest_controller import BacktestController
from modules.controller.object import BacktestConfigRequest, BacktestRunRequest
from modules.repositories.models import BacktestRunRecord


class _FakeBacktestRunService:
    def __init__(self) -> None:
        self.run_args = None

    def run(self, *, strategy_id, strategy_params, config):
        self.run_args = {
            "strategy_id": strategy_id,
            "strategy_params": strategy_params,
            "config": config,
        }
        return BacktestRunRecord(
            id=1,
            strategy_id=strategy_id,
            strategy_params=strategy_params,
            config=config,
            status="success",
            result_json={"summary": {"final_equity": 1000.0}},
            analysis_json={"summary": {"total_return": 0.0}},
            created_at="2026-10-13 10:00:00",
            updated_at="2026-10-13 10:00:01",
        )

    def list_recent(self, *, limit: int = 20):
        return [{"id": 1, "status": "success", "summary": {"final_equity": 1000.0}}]

    def get(self, run_id: int):
        return BacktestRunRecord(
            id=run_id,
            strategy_id="buy_and_hold",
            strategy_params={},
            config={"start_date": "2025-01-01", "end_date": "2025-12-31"},
            status="success",
            result_json={"summary": {"final_equity": 1000.0}},
            analysis_json={"summary": {"total_return": 0.0}},
            created_at="2026-10-13 10:00:00",
            updated_at="2026-10-13 10:00:01",
        )


class BacktestControllerTest(unittest.TestCase):
    def test_run_delegates_request_to_service(self) -> None:
        controller = BacktestController()
        fake_service = _FakeBacktestRunService()
        controller.service = fake_service

        response = controller.run(
            BacktestRunRequest(
                strategy_id="buy_and_hold",
                strategy_params={"instrument_ids": ["000001.SZ"]},
                config=BacktestConfigRequest(
                    start_date="2025-01-01",
                    end_date="2025-12-31",
                    initial_cash=1000.0,
                ),
            )
        )

        self.assertEqual(response.status, "success")
        self.assertEqual(fake_service.run_args["strategy_id"], "buy_and_hold")
        self.assertEqual(
            fake_service.run_args["strategy_params"],
            {"instrument_ids": ["000001.SZ"]},
        )
        self.assertEqual(fake_service.run_args["config"]["initial_cash"], 1000.0)

    def test_list_and_detail_delegate_to_service(self) -> None:
        controller = BacktestController()
        controller.service = _FakeBacktestRunService()

        runs = controller.list_runs(limit=10)
        detail = controller.get_detail(run_id=1)

        self.assertEqual(runs[0]["id"], 1)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail.id, 1)
        self.assertEqual(detail.result_json["summary"]["final_equity"], 1000.0)


if __name__ == "__main__":
    unittest.main()
