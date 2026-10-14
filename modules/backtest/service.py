from __future__ import annotations

from dataclasses import asdict
from typing import Any

from modules.backtest.analyzer import BacktestAnalyzer
from modules.backtest.engine import BacktestEngine
from modules.backtest.models import BacktestConfig
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import BacktestRunRecord
from modules.strategies.factory import create_strategy


class BacktestRunService:
    """管理回测执行实例生命周期，并持久化结果。"""

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        engine: BacktestEngine | None = None,
        analyzer: BacktestAnalyzer | None = None,
    ) -> None:
        """绑定数据库、回测引擎和分析器。"""
        self.database = database
        self.analyzer = analyzer or BacktestAnalyzer()
        self.engine = engine or BacktestEngine(database, analyzer=self.analyzer)

    def run(
        self,
        *,
        strategy_id: str,
        strategy_params: dict[str, Any],
        config: dict[str, Any],
    ) -> BacktestRunRecord:
        """创建实例、同步执行回测，并保存回测结果和分析结果。"""
        run_record = self._create_run(
            strategy_id=strategy_id,
            strategy_params=strategy_params,
            config=config,
        )
        run_id = self._require_id(run_record)
        self._mark_running(run_id)

        try:
            backtest_config = BacktestConfig(**config)
            strategy = create_strategy(strategy_id, strategy_params)
            result = self.engine.run(strategy, backtest_config)
            analysis = self.analyzer.analyze(result)
        except Exception as exc:
            return self._complete_failure(run_id=run_id, error_summary=str(exc))

        return self._complete_success(
            run_id=run_id,
            result_json=asdict(result),
            analysis_json=asdict(analysis),
        )

    def list_recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """返回最近回测实例的轻量摘要。"""
        with RepositorySession(self.database) as repositories:
            records = repositories.backtest_run.list_recent(limit=limit)
        return [self._to_summary(record) for record in records]

    def get(self, run_id: int) -> BacktestRunRecord | None:
        """读取某次回测实例详情。"""
        with RepositorySession(self.database) as repositories:
            return repositories.backtest_run.get(run_id)

    def _create_run(
        self,
        *,
        strategy_id: str,
        strategy_params: dict[str, Any],
        config: dict[str, Any],
    ) -> BacktestRunRecord:
        with RepositorySession(self.database, transactional=True) as repositories:
            return repositories.backtest_run.create(
                strategy_id=strategy_id,
                strategy_params=strategy_params,
                config=config,
            )

    def _mark_running(self, run_id: int) -> BacktestRunRecord:
        with RepositorySession(self.database, transactional=True) as repositories:
            return repositories.backtest_run.mark_running(run_id)

    def _complete_success(
        self,
        *,
        run_id: int,
        result_json: dict[str, Any],
        analysis_json: dict[str, Any],
    ) -> BacktestRunRecord:
        with RepositorySession(self.database, transactional=True) as repositories:
            return repositories.backtest_run.complete_success(
                run_id=run_id,
                result_json=result_json,
                analysis_json=analysis_json,
            )

    def _complete_failure(
        self,
        *,
        run_id: int,
        error_summary: str,
    ) -> BacktestRunRecord:
        with RepositorySession(self.database, transactional=True) as repositories:
            return repositories.backtest_run.complete_failure(
                run_id=run_id,
                error_summary=error_summary,
            )

    def _to_summary(self, record: BacktestRunRecord) -> dict[str, Any]:
        result_summary = None
        analysis_summary = None
        if record.result_json is not None:
            result_summary = record.result_json.get("summary")
        if record.analysis_json is not None:
            analysis_summary = record.analysis_json.get("summary")
        return {
            "id": record.id,
            "strategy_id": record.strategy_id,
            "status": record.status,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "error_summary": record.error_summary,
            "summary": analysis_summary or result_summary,
        }

    def _require_id(self, record: BacktestRunRecord) -> int:
        if record.id is None:
            raise RuntimeError("backtest run id is missing")
        return record.id
