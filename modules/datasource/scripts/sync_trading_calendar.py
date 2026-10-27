from __future__ import annotations

import json

import typer

from modules.datasource.adaptors import AdapterType
from modules.datasource.pipeline import TradingCalendarPipeline
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.utils.time_util import now_shanghai

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def _resolve_date_range(
    database: SQLiteDatabase,
    *,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, str]:
    if start_date or end_date:
        if not start_date or not end_date:
            raise typer.BadParameter("--start-date 和 --end-date 需要同时指定")
        return start_date, end_date

    with RepositorySession(database) as repositories:
        latest_trade_date = repositories.trading_calendar.get_latest_trade_date()
    if latest_trade_date is None:
        raise typer.BadParameter("首次同步交易日历需要指定 --start-date 和 --end-date")
    return latest_trade_date, now_shanghai().date().isoformat()


@app.command()
def main(
    start_date: str | None = typer.Option(None, "--start-date"),
    end_date: str | None = typer.Option(None, "--end-date"),
    adapter: AdapterType = typer.Option(
        "akshare", "--adapter", help="选择数据源 adapter"
    ),
) -> None:
    from modules.app import App

    runtime = App()
    pipeline = TradingCalendarPipeline(runtime.database)
    start_date, end_date = _resolve_date_range(
        runtime.database,
        start_date=start_date,
        end_date=end_date,
    )
    result = pipeline.run(
        adapter,
        start_date=start_date,
        end_date=end_date,
    )
    typer.echo(
        json.dumps(
            {
                "batch_id": result.id,
                "batch_key": result.batch_key,
                "status": result.status,
                "row_count_raw": result.raw_count,
                "row_count_loaded": result.loaded_count,
                "row_count_rejected": result.rejected_count,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    app()
