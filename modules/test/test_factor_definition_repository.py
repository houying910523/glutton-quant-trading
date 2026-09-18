from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.utils.time_util import format_timestamp
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import FactorDefinitionRecord
from modules.repositories.schema import SQLiteSchemaManager


class FactorDefinitionRepositoryTest(unittest.TestCase):
    def test_schema_initializes_builtin_seed_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            SQLiteSchemaManager(database).initialize()

            with RepositorySession(database) as repositories:
                definitions = repositories.factor_definition.list_active()

            self.assertEqual(
                [item.factor_id for item in definitions],
                ["ma_5_10_20_30_60_120", "macd_12_26_9", "boll_20_2"],
            )

    def test_upsert_and_get_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            SQLiteSchemaManager(database).initialize()
            now = format_timestamp()

            record = FactorDefinitionRecord(
                factor_id="ma_20",
                version="v1",
                factor_name="20日均线",
                category="trend",
                compute_ref=("modules.factors.builtin.trend:SimpleMovingAverageFactor"),
                params={"window": 20},
                output_columns=["ma_20"],
                storage_key="ma/v1/window_20",
                description="用于趋势研究的 20 日均线",
                status="active",
                created_at=now,
                updated_at=now,
            )

            with RepositorySession(database, transactional=True) as repositories:
                persisted = repositories.factor_definition.upsert(record)

            self.assertIsNotNone(persisted.id)
            self.assertEqual(persisted.factor_id, "ma_20")

            with RepositorySession(database) as repositories:
                fetched = repositories.factor_definition.get("ma_20", version="v1")

            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.factor_name, "20日均线")
            self.assertEqual(fetched.params, {"window": 20})
            self.assertEqual(fetched.output_columns, ["ma_20"])
            self.assertEqual(fetched.storage_key, "ma/v1/window_20")
            self.assertIsNone(fetched.last_materialized_date)

    def test_set_last_materialized_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            SQLiteSchemaManager(database).initialize()

            with RepositorySession(database, transactional=True) as repositories:
                repositories.factor_definition.set_last_materialized_date(
                    factor_id="ma_5_10_20_30_60_120",
                    version="v1",
                    last_materialized_date="2024-01-25",
                )

            with RepositorySession(database) as repositories:
                fetched = repositories.factor_definition.get(
                    "ma_5_10_20_30_60_120", version="v1"
                )

            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.last_materialized_date, "2024-01-25")

    def test_list_active_filters_disabled_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            database = SQLiteDatabase(root / "glutton.db")
            SQLiteSchemaManager(database).initialize()
            now = format_timestamp()

            records = [
                FactorDefinitionRecord(
                    factor_id="ma_20",
                    version="v1",
                    factor_name="20日均线",
                    category="trend",
                    compute_ref=(
                        "modules.factors.builtin.trend:SimpleMovingAverageFactor"
                    ),
                    params={"window": 20},
                    output_columns=["ma_20"],
                    storage_key="ma/v1/window_20",
                    status="active",
                    created_at=now,
                    updated_at=now,
                ),
                FactorDefinitionRecord(
                    factor_id="rsi_14",
                    version="v1",
                    factor_name="RSI(14)",
                    category="momentum",
                    compute_ref="modules.factors.builtin.momentum:RsiFactor",
                    params={"window": 14},
                    output_columns=["rsi_14"],
                    storage_key="rsi/v1/window_14",
                    status="disabled",
                    created_at=now,
                    updated_at=now,
                ),
            ]

            with RepositorySession(database, transactional=True) as repositories:
                repositories.factor_definition.upsert_many(records)

            with RepositorySession(database) as repositories:
                active = repositories.factor_definition.list_active()
                trend = repositories.factor_definition.list_by_category("trend")
                momentum_all = repositories.factor_definition.list_by_category(
                    "momentum", active_only=False
                )

            self.assertEqual(
                [item.factor_id for item in active],
                ["ma_20", "ma_5_10_20_30_60_120", "macd_12_26_9", "boll_20_2"],
            )
            self.assertEqual(
                [item.factor_id for item in trend],
                ["ma_20", "ma_5_10_20_30_60_120", "macd_12_26_9"],
            )
            self.assertEqual([item.factor_id for item in momentum_all], ["rsi_14"])


if __name__ == "__main__":
    unittest.main()
