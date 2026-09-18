from __future__ import annotations

import json

import typer

from modules.datasource.adaptors import AdapterType
from modules.datasource.jobs.common import JobRuntime
from modules.datasource.pipeline import DailyQuotePipeline

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


@app.command()
def main(
    stock_id: int | None = typer.Option(None, "--stock-id"),
    symbol: str | None = typer.Option(None, "--symbol"),
    adapter: AdapterType = typer.Option(
        "akshare", "--adapter", help="选择数据源 adapter"
    ),
) -> None:
    runtime = JobRuntime()
    pipeline = DailyQuotePipeline(runtime.database, runtime.raw_store)
    result = pipeline.run(
        adaptor_type=adapter,
        sync_mode="incremental",
        stock_id=stock_id,
        symbol=symbol,
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
