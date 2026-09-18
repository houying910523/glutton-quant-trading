from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import typer

from modules.config import DEFAULT_DB_PATH, DEFAULT_FACTOR_ROOT, resolve_project_path
from modules.factors.base import load_factor
from modules.factors.models import FactorDefinition, FactorSpec
from modules.factors.sqlite_market_loader import SQLiteMarketLoader
from modules.factors.storage import ParquetFactorStore
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import FactorDefinitionRecord
from modules.repositories.schema import SQLiteSchemaManager
from modules.utils.time_util import format_date, parse_date

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    help="从 SQLite 日线行情刷新因子 Parquet 分区。",
)


def refresh_factors(
    database: SQLiteDatabase,
    factor_root: Path,
    *,
    factor_ids: list[str] | None,
    start_date: date,
    end_date: date,
    instruments: list[str] | None = None,
) -> list[dict[str, Any]]:
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    SQLiteSchemaManager(database).initialize()
    loader = SQLiteMarketLoader(database)
    store = ParquetFactorStore(factor_root)

    with RepositorySession(database) as repositories:
        definitions = _load_definitions(repositories, factor_ids)

    results: list[dict[str, Any]] = []
    for definition in definitions:
        result = refresh_factor_definition(
            definition,
            loader,
            store,
            start_date=start_date,
            end_date=end_date,
            instruments=instruments,
        )
        if result["last_materialized_date"] is not None:
            with RepositorySession(database, transactional=True) as repositories:
                repositories.factor_definition.set_last_materialized_date(
                    factor_id=definition.factor_id,
                    version=definition.version,
                    last_materialized_date=result["last_materialized_date"],
                )
        results.append(result)
    return results


def refresh_factor_definition(
    definition: FactorDefinition,
    loader: SQLiteMarketLoader,
    store: ParquetFactorStore,
    *,
    start_date: date,
    end_date: date,
    instruments: list[str] | None = None,
) -> dict[str, Any]:
    factor = load_factor(definition)
    spec = factor.spec(definition.params)
    _validate_spec(definition, spec)

    partitions_written: list[str] = []
    rows_written = 0
    last_materialized_date: date | None = None
    for month_start in _iter_month_starts(start_date, end_date):
        month_end = _month_end(month_start)
        load_start = month_start - timedelta(days=_history_padding_days(spec))
        stock_daily = loader.load_stock_daily(
            start_date=load_start,
            end_date=month_end,
            instruments=instruments,
            columns=spec.required_columns,
        )
        if stock_daily.is_empty():
            continue

        computed = factor.compute(stock_daily, definition.params)
        output = _normalize_output_frame(
            computed,
            output_columns=definition.output_columns,
            start_date=month_start,
            end_date=month_end,
        )
        if output.is_empty():
            continue

        path = store.write_month_partition(
            storage_key=definition.storage_key,
            frame=output,
            year=month_start.year,
            month=month_start.month,
        )
        partitions_written.append(str(path))
        rows_written += output.height
        partition_last_date = output["trade_date"].max()
        if partition_last_date is not None and (
            last_materialized_date is None
            or partition_last_date > last_materialized_date
        ):
            last_materialized_date = partition_last_date

    return {
        "factor_id": definition.factor_id,
        "factor_name": definition.factor_name,
        "version": definition.version,
        "storage_key": definition.storage_key,
        "partitions_written": partitions_written,
        "rows_written": rows_written,
        "last_materialized_date": format_date(last_materialized_date),
    }


@app.command()
def main(
    factor_id: list[str] | None = typer.Option(
        None,
        "--factor-id",
        help="可重复指定；仅刷新这些 active 因子，例如 --factor-id ma_20 --factor-id macd_12_26_9",
    ),
    all_active: bool = typer.Option(
        False,
        "--all-active",
        help="刷新 factor_definition 中全部 active 因子。",
    ),
    start_date: str = typer.Option(
        ...,
        "--start-date",
        help="刷新起始交易日，支持 YYYY-MM-DD 或 YYYYMMDD。",
    ),
    end_date: str | None = typer.Option(
        None,
        "--end-date",
        help="刷新结束交易日；不传时默认等于 --start-date。",
    ),
    instrument: list[str] | None = typer.Option(
        None,
        "--instrument",
        help="可重复指定；仅刷新这些 instrument_id，例如 600519.SH。",
    ),
) -> None:
    if factor_id and all_active:
        raise typer.BadParameter("--factor-id and --all-active cannot be used together")
    if not factor_id and not all_active:
        raise typer.BadParameter("please provide --factor-id or --all-active")

    parsed_start = parse_date(start_date)
    parsed_end = parse_date(end_date) if end_date else parsed_start
    if parsed_start is None or parsed_end is None:
        raise ValueError("start_date and end_date must be valid dates")

    resolved_db_path = resolve_project_path(DEFAULT_DB_PATH)
    resolved_factor_root = resolve_project_path(DEFAULT_FACTOR_ROOT)
    database = SQLiteDatabase(resolved_db_path)
    results = refresh_factors(
        database,
        resolved_factor_root,
        factor_ids=None if all_active else factor_id,
        start_date=parsed_start,
        end_date=parsed_end,
        instruments=instrument,
    )
    _emit_refresh_logs(
        results,
        factor_ids=factor_id,
        all_active=all_active,
        start_date=parsed_start,
        end_date=parsed_end,
        instruments=instrument,
        db_path=resolved_db_path,
        factor_root=resolved_factor_root,
    )
    typer.echo(json.dumps(results, ensure_ascii=False, indent=2))


def _load_definitions(
    repositories: RepositorySession,
    factor_ids: list[str] | None,
) -> list[FactorDefinition]:
    if not factor_ids:
        records = repositories.factor_definition.list_active()
        return [_to_definition(record) for record in records]

    definitions: list[FactorDefinition] = []
    seen: set[str] = set()
    for factor_id in factor_ids:
        normalized = factor_id.strip()
        if not normalized or normalized in seen:
            continue
        record = repositories.factor_definition.get(normalized)
        if record is None:
            raise ValueError(f"factor definition not found: {normalized}")
        if record.status != "active":
            raise ValueError(f"factor definition is not active: {normalized}")
        definitions.append(_to_definition(record))
        seen.add(normalized)
    return definitions


def _to_definition(record: FactorDefinitionRecord) -> FactorDefinition:
    return FactorDefinition(
        factor_id=record.factor_id,
        version=record.version,
        factor_name=record.factor_name,
        category=record.category,
        compute_ref=record.compute_ref,
        params=record.params,
        output_columns=record.output_columns,
        storage_key=record.storage_key,
        description=record.description,
        status=record.status,
        last_materialized_date=record.last_materialized_date,
    )


def _emit_refresh_logs(
    results: list[dict[str, Any]],
    *,
    factor_ids: list[str] | None,
    all_active: bool,
    start_date: date,
    end_date: date,
    instruments: list[str] | None,
    db_path: Path,
    factor_root: Path,
) -> None:
    refresh_mode = "all_active" if all_active else "selected"
    target = ", ".join(factor_ids or []) if factor_ids else "ALL_ACTIVE"
    instrument_scope = ", ".join(instruments or []) if instruments else "ALL"
    typer.echo(
        (
            "[refresh_factors] "
            f"mode={refresh_mode} target={target} "
            f"date_range={start_date.isoformat()}..{end_date.isoformat()} "
            f"instruments={instrument_scope} db_path={db_path} factor_root={factor_root}"
        ),
        err=True,
    )

    total_rows = 0
    total_partitions = 0
    for result in results:
        partition_count = len(result["partitions_written"])
        total_rows += int(result["rows_written"])
        total_partitions += partition_count
        typer.echo(
            (
                "[refresh_factors] "
                f"factor_id={result['factor_id']} version={result['version']} "
                f"rows_written={result['rows_written']} partitions_written={partition_count} "
                f"last_materialized_date={result['last_materialized_date']} "
                f"storage_key={result['storage_key']}"
            ),
            err=True,
        )

    typer.echo(
        (
            "[refresh_factors] "
            f"factors={len(results)} total_rows_written={total_rows} "
            f"total_partitions_written={total_partitions}"
        ),
        err=True,
    )


def _validate_spec(definition: FactorDefinition, spec: FactorSpec) -> None:
    if spec.output_columns != definition.output_columns:
        raise ValueError(
            "factor output columns do not match definition: "
            f"expected={definition.output_columns}, actual={spec.output_columns}"
        )


def _normalize_output_frame(
    frame: pl.DataFrame,
    *,
    output_columns: list[str],
    start_date: date,
    end_date: date,
) -> pl.DataFrame:
    expected_columns = ["trade_date", "instrument_id", *output_columns]
    missing = [column for column in expected_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"factor compute result missing columns: {missing}")

    return (
        frame.select(expected_columns)
        .filter(
            (pl.col("trade_date") >= pl.lit(start_date))
            & (pl.col("trade_date") <= pl.lit(end_date))
        )
        .sort(["trade_date", "instrument_id"])
        .unique(
            subset=["trade_date", "instrument_id"],
            keep="last",
            maintain_order=True,
        )
    )


def _history_padding_days(spec: FactorSpec) -> int:
    required = max(spec.required_history_bars, 0)
    if required == 0:
        return 0
    return max(required * 3, required + 31)


def _iter_month_starts(start_date: date, end_date: date) -> list[date]:
    current = date(start_date.year, start_date.month, 1)
    month_limit = date(end_date.year, end_date.month, 1)
    values: list[date] = []
    while current <= month_limit:
        values.append(current)
        current = _next_month(current)
    return values


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _month_end(value: date) -> date:
    return _next_month(date(value.year, value.month, 1)) - timedelta(days=1)


if __name__ == "__main__":
    app()
