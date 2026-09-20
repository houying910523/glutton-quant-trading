from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import typer
from tqdm import tqdm

from modules.config import DEFAULT_DB_PATH, DEFAULT_INDICATOR_ROOT, resolve_project_path
from modules.indicators.base import load_indicator
from modules.indicators.models import IndicatorDefinition, IndicatorSpec
from modules.datasource.service.stock_daily_service import StockDailyService
from modules.indicators.storage import IndicatorStore
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import IndicatorRecord
from modules.repositories.schema import SQLiteSchemaManager
from modules.utils.time_util import format_date, parse_date

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    help="从 SQLite 日线行情刷新因子 Parquet 分区。",
)


def refresh_factors(
    database: SQLiteDatabase,
    indicator_root: Path,
    *,
    indicator_ids: list[str] | None,
    start_date: date,
    end_date: date,
    instruments: list[str] | None = None,
    force: bool = False,
) -> list[dict[str, Any]]:
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    SQLiteSchemaManager(database).initialize()
    loader = StockDailyService(database)
    store = IndicatorStore(indicator_root)

    with RepositorySession(database) as repositories:
        indicator_definitions = _load_indicator_definitions(repositories, indicator_ids)

    total_months = sum(
        len(
            _pending_month_ranges(
                indicator_definition,
                _resolve_effective_start_date(
                    indicator_definition,
                    start_date,
                    end_date,
                    force=force,
                ),
                end_date,
                force=force,
            )
        )
        for indicator_definition in indicator_definitions
    )
    progress = tqdm(
        total=total_months,
        ncols=100,
        desc="Refreshing factors",
        unit="month",
        leave=True,
        disable=not sys.stderr.isatty(),
    )

    results: list[dict[str, Any]] = []
    try:
        for indicator_definition in indicator_definitions:
            progress.set_postfix_str(
                f"{indicator_definition.indicator_id}@{indicator_definition.version}"
            )

            def on_month_processed(_: date) -> None:
                progress.update(1)

            def on_month_materialized(
                materialized_date: date,
                *,
                current_indicator_definition: IndicatorDefinition = (
                    indicator_definition
                ),
            ) -> None:
                formatted_date = format_date(materialized_date)
                if formatted_date is None:
                    return
                with RepositorySession(database, transactional=True) as repositories:
                    repositories.indicator.set_last_materialized_date(
                        indicator_id=current_indicator_definition.indicator_id,
                        version=current_indicator_definition.version,
                        last_materialized_date=formatted_date,
                    )
                current_indicator_definition.last_materialized_date = formatted_date

            effective_start_date = _resolve_effective_start_date(
                indicator_definition,
                start_date,
                end_date,
                force=force,
            )
            result = refresh_indicator_definition(
                indicator_definition,
                loader,
                store,
                start_date=effective_start_date,
                end_date=end_date,
                instruments=instruments,
                force=force,
                on_month_processed=on_month_processed,
                on_month_materialized=on_month_materialized,
            )
            results.append(result)
    finally:
        progress.close()
    return results


def refresh_indicator_definition(
    indicator_definition: IndicatorDefinition,
    loader: StockDailyService,
    store: IndicatorStore,
    *,
    start_date: date,
    end_date: date,
    instruments: list[str] | None = None,
    force: bool = False,
    on_month_processed: Callable[[date], None] | None = None,
    on_month_materialized: Callable[[date], None] | None = None,
) -> dict[str, Any]:
    indicator = load_indicator(indicator_definition)
    spec = indicator.spec(indicator_definition.params)
    _validate_spec(indicator_definition, spec)

    partitions_written: list[str] = []
    rows_written = 0
    last_materialized_date = parse_date(indicator_definition.last_materialized_date)
    pending_month_ranges = _pending_month_ranges(
        indicator_definition,
        start_date,
        end_date,
        force=force,
    )
    for month_start, partition_start_date, partition_end_date in pending_month_ranges:
        load_start = partition_start_date - timedelta(days=_history_padding_days(spec))
        stock_daily = loader.load_stock_daily(
            start_date=load_start,
            end_date=partition_end_date,
            instruments=instruments,
            columns=spec.required_columns,
        )
        if not stock_daily.is_empty():
            computed = indicator.compute(stock_daily, indicator_definition.params)
            output = _normalize_output_frame(
                computed,
                output_columns=indicator_definition.output_columns,
                start_date=partition_start_date,
                end_date=partition_end_date,
            )
            if not output.is_empty():
                frame_to_write = output
                if partition_start_date > month_start:
                    existing_partition = _read_existing_month_partition(
                        store,
                        storage_key=indicator_definition.storage_key,
                        year=month_start.year,
                        month=month_start.month,
                    )
                    if (
                        existing_partition is not None
                        and not existing_partition.is_empty()
                    ):
                        frame_to_write = _merge_partition_frames(
                            existing_partition,
                            output,
                            output_columns=indicator_definition.output_columns,
                        )
                path = store.write_month_partition(
                    storage_key=indicator_definition.storage_key,
                    frame=frame_to_write,
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
                    if on_month_materialized is not None:
                        on_month_materialized(partition_last_date)

        if on_month_processed is not None:
            on_month_processed(month_start)

    return {
        "indicator_id": indicator_definition.indicator_id,
        "indicator_name": indicator_definition.indicator_name,
        "version": indicator_definition.version,
        "storage_key": indicator_definition.storage_key,
        "partitions_written": partitions_written,
        "rows_written": rows_written,
        "last_materialized_date": format_date(last_materialized_date),
    }


@app.command()
def main(
    indicator_id: list[str] | None = typer.Option(
        None,
        "--indicator-id",
        help="可重复指定；仅刷新这些 active 指标，例如 --indicator-id ma_20 --indicator-id macd_12_26_9",
    ),
    all_active: bool = typer.Option(
        False,
        "--all-active",
        help="刷新 indicator_definition 中全部 active 因子。",
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
    force: bool = typer.Option(
        False,
        "--force",
        help="为 true 时忽略 last_materialized_date 对起始日期的自动推进，按传入区间强制重算。",
    ),
) -> None:
    if indicator_id and all_active:
        raise typer.BadParameter(
            "--indicator-id and --all-active cannot be used together"
        )
    if not indicator_id and not all_active:
        raise typer.BadParameter("please provide --indicator-id or --all-active")

    parsed_start = parse_date(start_date)
    parsed_end = parse_date(end_date) if end_date else parsed_start
    if parsed_start is None or parsed_end is None:
        raise ValueError("start_date and end_date must be valid dates")

    resolved_db_path = resolve_project_path(DEFAULT_DB_PATH)
    resolved_indicator_root = resolve_project_path(DEFAULT_INDICATOR_ROOT)
    database = SQLiteDatabase(resolved_db_path)
    results = refresh_factors(
        database,
        resolved_indicator_root,
        indicator_ids=None if all_active else indicator_id,
        start_date=parsed_start,
        end_date=parsed_end,
        instruments=instrument,
        force=force,
    )
    _emit_refresh_logs(
        results,
        indicator_ids=indicator_id,
        all_active=all_active,
        start_date=parsed_start,
        end_date=parsed_end,
        instruments=instrument,
        force=force,
        db_path=resolved_db_path,
        indicator_root=resolved_indicator_root,
    )
    typer.echo(json.dumps(results, ensure_ascii=False, indent=2))


def _load_indicator_definitions(
    repositories: RepositorySession,
    indicator_ids: list[str] | None,
) -> list[IndicatorDefinition]:
    if not indicator_ids:
        records = repositories.indicator.list_active()
        return [_to_indicator_definition(record) for record in records]

    indicator_definitions: list[IndicatorDefinition] = []
    seen: set[str] = set()
    for indicator_id in indicator_ids:
        normalized = indicator_id.strip()
        if not normalized or normalized in seen:
            continue
        record = repositories.indicator.get(normalized)
        if record is None:
            raise ValueError(f"indicator definition not found: {normalized}")
        if record.status != "active":
            raise ValueError(f"indicator definition is not active: {normalized}")
        indicator_definitions.append(_to_indicator_definition(record))
        seen.add(normalized)
    return indicator_definitions


def _to_indicator_definition(
    record: IndicatorRecord,
) -> IndicatorDefinition:
    return IndicatorDefinition(
        indicator_id=record.indicator_id,
        version=record.version,
        indicator_name=record.indicator_name,
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
    indicator_ids: list[str] | None,
    all_active: bool,
    start_date: date,
    end_date: date,
    instruments: list[str] | None,
    force: bool,
    db_path: Path,
    indicator_root: Path,
) -> None:
    refresh_mode = "all_active" if all_active else "selected"
    target = ", ".join(indicator_ids or []) if indicator_ids else "ALL_ACTIVE"
    instrument_scope = ", ".join(instruments or []) if instruments else "ALL"
    typer.echo(
        (
            "[refresh_factors] "
            f"mode={refresh_mode} target={target} "
            f"date_range={start_date.isoformat()}..{end_date.isoformat()} "
            f"force={force} instruments={instrument_scope} "
            f"db_path={db_path} indicator_root={indicator_root}"
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
                f"indicator_id={result['indicator_id']} version={result['version']} "
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


def _resolve_effective_start_date(
    indicator_definition: IndicatorDefinition,
    start_date: date,
    end_date: date,
    *,
    force: bool,
) -> date:
    if force:
        return start_date

    last_materialized_date = parse_date(indicator_definition.last_materialized_date)
    if last_materialized_date is None:
        return start_date
    if start_date < last_materialized_date < end_date:
        return last_materialized_date
    return start_date


def _pending_month_ranges(
    indicator_definition: IndicatorDefinition,
    start_date: date,
    end_date: date,
    *,
    force: bool = False,
) -> list[tuple[date, date, date]]:
    last_materialized_date = (
        None if force else parse_date(indicator_definition.last_materialized_date)
    )
    if last_materialized_date is None:
        return [
            (
                month_start,
                month_start,
                min(_month_end(month_start), end_date),
            )
            for month_start in _iter_month_starts(start_date, end_date)
        ]

    resume_date = max(start_date, last_materialized_date + timedelta(days=1))
    if resume_date > end_date:
        return []

    pending_ranges: list[tuple[date, date, date]] = []
    first_month_start = date(resume_date.year, resume_date.month, 1)
    for month_start in _iter_month_starts(resume_date, end_date):
        partition_start_date = (
            resume_date if month_start == first_month_start else month_start
        )
        pending_ranges.append(
            (
                month_start,
                partition_start_date,
                min(_month_end(month_start), end_date),
            )
        )
    return pending_ranges


def _read_existing_month_partition(
    store: IndicatorStore,
    *,
    storage_key: str,
    year: int,
    month: int,
) -> pl.DataFrame | None:
    path = store.partition_path(storage_key, year=year, month=month)
    if not path.exists():
        return None
    return pl.read_parquet(path)


def _merge_partition_frames(
    existing: pl.DataFrame,
    updates: pl.DataFrame,
    *,
    output_columns: list[str],
) -> pl.DataFrame:
    expected_columns = ["trade_date", "instrument_id", *output_columns]
    return (
        pl.concat(
            [
                existing.select(expected_columns),
                updates.select(expected_columns),
            ],
            how="vertical_relaxed",
        )
        .sort(["trade_date", "instrument_id"])
        .unique(
            subset=["trade_date", "instrument_id"],
            keep="last",
            maintain_order=True,
        )
    )


def _validate_spec(
    indicator_definition: IndicatorDefinition, spec: IndicatorSpec
) -> None:
    if spec.output_columns != indicator_definition.output_columns:
        raise ValueError(
            "factor output columns do not match definition: "
            f"expected={indicator_definition.output_columns}, actual={spec.output_columns}"
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


def _history_padding_days(spec: IndicatorSpec) -> int:
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
