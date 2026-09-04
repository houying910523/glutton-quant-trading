from __future__ import annotations

import json

import typer

from modules.datasource.adaptors import AdapterType
from modules.datasource.jobs.common import JobRuntime
from modules.datasource.pipeline import DailyQuotePipeline

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


@app.command()
def main(
    start_date: str = typer.Option(..., "--start-date"),
    end_date: str = typer.Option(..., "--end-date"),
    symbols: str | None = typer.Option(None, "--symbols"),
    refresh: bool = typer.Option(False, "--refresh"),
    adapter: AdapterType = typer.Option(
        "akshare", "--adapter", help="选择数据源 adapter"
    ),
) -> None:
    runtime = JobRuntime()
    pipeline = DailyQuotePipeline(runtime.database, runtime.raw_store)
    result = pipeline.run(
        adaptor_type=adapter,
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        refresh=refresh,
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
