from __future__ import annotations

import json
from typing import Any

from modules.repositories.base import SQLiteRepository
from modules.repositories.models import BacktestRunRecord
from modules.utils.time_util import format_timestamp


class BacktestRunRepository(SQLiteRepository):
    """管理回测执行实例及其持久化结果。"""

    def create(
        self,
        *,
        strategy_id: str,
        strategy_params: dict[str, Any],
        config: dict[str, Any],
    ) -> BacktestRunRecord:
        """创建 pending 状态的回测实例。"""
        now = format_timestamp()
        cursor = self._connection.execute(
            """
            INSERT INTO backtest_runs (
                strategy_id, strategy_params, config, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                strategy_id,
                self._dump_json(strategy_params),
                self._dump_json(config),
                "pending",
                now,
                now,
            ),
        )
        record = self.get(int(cursor.lastrowid))
        if record is None:
            raise RuntimeError("backtest run creation failed")
        return record

    def mark_running(self, run_id: int) -> BacktestRunRecord:
        """把回测实例标记为 running。"""
        now = format_timestamp()
        self._connection.execute(
            """
            UPDATE backtest_runs
            SET status = 'running',
                started_at = COALESCE(started_at, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (now, now, run_id),
        )
        return self._require(run_id)

    def complete_success(
        self,
        *,
        run_id: int,
        result_json: dict[str, Any],
        analysis_json: dict[str, Any],
    ) -> BacktestRunRecord:
        """保存回测结果和分析结果，并把实例标记为 success。"""
        now = format_timestamp()
        self._connection.execute(
            """
            UPDATE backtest_runs
            SET status = 'success',
                finished_at = ?,
                result_json = ?,
                analysis_json = ?,
                error_summary = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (
                now,
                self._dump_json(result_json),
                self._dump_json(analysis_json),
                now,
                run_id,
            ),
        )
        return self._require(run_id)

    def complete_failure(
        self,
        *,
        run_id: int,
        error_summary: str,
    ) -> BacktestRunRecord:
        """保存失败原因，并把实例标记为 failed。"""
        now = format_timestamp()
        self._connection.execute(
            """
            UPDATE backtest_runs
            SET status = 'failed',
                finished_at = ?,
                error_summary = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, error_summary, now, run_id),
        )
        return self._require(run_id)

    def get(self, run_id: int) -> BacktestRunRecord | None:
        """按 ID 读取回测实例详情。"""
        row = self._connection.execute(
            """
            SELECT *
            FROM backtest_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_recent(self, *, limit: int = 20) -> list[BacktestRunRecord]:
        """读取最近的回测实例。"""
        rows = self._connection.execute(
            """
            SELECT *
            FROM backtest_runs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _require(self, run_id: int) -> BacktestRunRecord:
        record = self.get(run_id)
        if record is None:
            raise RuntimeError(f"backtest run not found: {run_id}")
        return record

    def _row_to_record(self, row: Any) -> BacktestRunRecord:
        return BacktestRunRecord(
            id=int(row["id"]),
            strategy_id=row["strategy_id"],
            strategy_params=self._load_json_dict(row["strategy_params"]),
            config=self._load_json_dict(row["config"]),
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            result_json=self._load_optional_json_dict(row["result_json"]),
            analysis_json=self._load_optional_json_dict(row["analysis_json"]),
            error_summary=row["error_summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @classmethod
    def _dump_json(cls, value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @classmethod
    def _load_json_dict(cls, value: str) -> dict[str, Any]:
        loaded = json.loads(value)
        if not isinstance(loaded, dict):
            raise ValueError("expected JSON object")
        return loaded

    @classmethod
    def _load_optional_json_dict(cls, value: str | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return cls._load_json_dict(value)
