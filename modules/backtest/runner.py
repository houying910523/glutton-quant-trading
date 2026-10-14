from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from modules.backtest.analyzer import BacktestAnalyzer
from modules.backtest.engine import BacktestEngine
from modules.backtest.models import (
    BacktestAnalyzeResult,
    BacktestConfig,
    BacktestResult,
)
from modules.repositories.database import SQLiteDatabase

if TYPE_CHECKING:
    from modules.strategies.base import BaseStrategy


@dataclass(frozen=True)
class BacktestRunArtifact:
    """一次回测运行返回的原始结果与分析结果。"""

    result: BacktestResult
    analysis: BacktestAnalyzeResult


class BacktestRunner:
    """对外提供一站式回测入口，组合 engine.run 和 analyzer.analyze。"""

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        engine: BacktestEngine | None = None,
        analyzer: BacktestAnalyzer | None = None,
    ) -> None:
        """绑定回测引擎与分析器；未传入时使用默认实现。"""
        self._database = database
        self._analyzer = analyzer or BacktestAnalyzer()
        self._engine = engine or BacktestEngine(database, analyzer=self._analyzer)

    def run(
        self,
        strategy: "BaseStrategy",
        config: BacktestConfig,
    ) -> BacktestRunArtifact:
        """执行策略回测并同步生成分析结果。"""
        backtest_result = self._engine.run(strategy, config)
        analysis = self._analyzer.analyze(backtest_result)
        return BacktestRunArtifact(result=backtest_result, analysis=analysis)
