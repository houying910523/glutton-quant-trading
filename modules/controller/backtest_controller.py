from modules.backtest.service import BacktestRunService
from modules.controller.base import get_mapping, post_mapping, rest_controller
from modules.controller.object import BacktestRunRequest
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import BacktestRunRecord


@rest_controller("/backtest")
class BacktestController:
    def __init__(self):
        self.database = SQLiteDatabase()
        self.service = BacktestRunService(self.database)

    @post_mapping("/run")
    def run(self, request: BacktestRunRequest) -> BacktestRunRecord:
        return self.service.run(
            strategy_id=request.strategy_id,
            strategy_params=request.strategy_params,
            config=request.config.model_dump(mode="json"),
        )

    @get_mapping("/list")
    def list_runs(self, limit: int = 20) -> list[dict]:
        return self.service.list_recent(limit=limit)

    @get_mapping("/detail")
    def get_detail(self, run_id: int) -> BacktestRunRecord | None:
        return self.service.get(run_id)
