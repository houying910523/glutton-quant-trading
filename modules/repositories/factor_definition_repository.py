from __future__ import annotations

import json
from typing import Any

from modules.utils.time_util import format_date, format_timestamp
from modules.repositories.base import SQLiteRepository
from modules.repositories.models import FactorDefinitionRecord


class FactorDefinitionRepository(SQLiteRepository):
    def upsert(self, record: FactorDefinitionRecord) -> FactorDefinitionRecord:
        records = self.upsert_many([record])
        return records[0]

    def upsert_many(
        self,
        records: list[FactorDefinitionRecord],
    ) -> list[FactorDefinitionRecord]:
        if not records:
            return []

        persisted: list[FactorDefinitionRecord] = []
        for record in records:
            created_at = record.created_at
            updated_at = record.updated_at
            if record.id is None:
                existing = self.get(record.factor_id, version=record.version)
                if existing is not None:
                    created_at = existing.created_at
            self._connection.execute(
                """
                INSERT INTO factor_definition (
                    factor_id,
                    version,
                    factor_name,
                    category,
                    compute_ref,
                    params,
                    output_columns,
                    storage_key,
                    description,
                    status,
                    last_materialized_date,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(factor_id, version) DO UPDATE SET
                    factor_name = excluded.factor_name,
                    category = excluded.category,
                    compute_ref = excluded.compute_ref,
                    params = excluded.params,
                    output_columns = excluded.output_columns,
                    storage_key = excluded.storage_key,
                    description = excluded.description,
                    status = excluded.status,
                    last_materialized_date = COALESCE(
                        excluded.last_materialized_date,
                        factor_definition.last_materialized_date
                    ),
                    updated_at = excluded.updated_at
                """,
                (
                    record.factor_id,
                    record.version,
                    record.factor_name,
                    record.category,
                    record.compute_ref,
                    self._dump_json(record.params),
                    self._dump_json(record.output_columns),
                    record.storage_key,
                    record.description,
                    record.status,
                    record.last_materialized_date,
                    created_at,
                    updated_at,
                ),
            )
            persisted_record = self.get(record.factor_id, version=record.version)
            if persisted_record is None:
                raise RuntimeError("factor definition upsert failed")
            persisted.append(persisted_record)
        return persisted

    def get(
        self,
        factor_id: str,
        version: str = "v1",
    ) -> FactorDefinitionRecord | None:
        row = self._connection.execute(
            """
            SELECT *
            FROM factor_definition
            WHERE factor_id = ?
              AND version = ?
            """,
            (factor_id, version),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_by_storage_key(self, storage_key: str) -> FactorDefinitionRecord | None:
        row = self._connection.execute(
            """
            SELECT *
            FROM factor_definition
            WHERE storage_key = ?
            """,
            (storage_key,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_all(self) -> list[FactorDefinitionRecord]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM factor_definition
            ORDER BY category, factor_id, version
            """
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_active(self) -> list[FactorDefinitionRecord]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM factor_definition
            WHERE status = 'active'
            ORDER BY category, factor_id, version
            """
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_by_category(
        self,
        category: str,
        *,
        active_only: bool = True,
    ) -> list[FactorDefinitionRecord]:
        if active_only:
            rows = self._connection.execute(
                """
                SELECT *
                FROM factor_definition
                WHERE category = ?
                  AND status = 'active'
                ORDER BY factor_id, version
                """,
                (category,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT *
                FROM factor_definition
                WHERE category = ?
                ORDER BY factor_id, version
                """,
                (category,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def set_last_materialized_date(
        self,
        *,
        factor_id: str,
        last_materialized_date: str,
        version: str = "v1",
    ) -> None:
        self._connection.execute(
            """
            UPDATE factor_definition
            SET last_materialized_date = ?,
                updated_at = ?
            WHERE factor_id = ?
              AND version = ?
            """,
            (
                format_date(last_materialized_date),
                format_timestamp(),
                factor_id,
                version,
            ),
        )

    def _row_to_record(self, row: Any) -> FactorDefinitionRecord:
        return FactorDefinitionRecord(
            id=int(row["id"]),
            factor_id=row["factor_id"],
            version=row["version"],
            factor_name=row["factor_name"],
            category=row["category"],
            compute_ref=row["compute_ref"],
            params=self._load_json_dict(row["params"]),
            output_columns=self._load_json_list(row["output_columns"]),
            storage_key=row["storage_key"],
            description=row["description"],
            status=row["status"],
            last_materialized_date=row["last_materialized_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @classmethod
    def _dump_json(cls, value: dict[str, object] | list[str]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @classmethod
    def _load_json_dict(cls, value: str) -> dict[str, object]:
        loaded = json.loads(value)
        if not isinstance(loaded, dict):
            raise ValueError("expected JSON object for params")
        return loaded

    @classmethod
    def _load_json_list(cls, value: str) -> list[str]:
        loaded = json.loads(value)
        if not isinstance(loaded, list) or not all(
            isinstance(item, str) for item in loaded
        ):
            raise ValueError("expected JSON string list for output_columns")
        return loaded
