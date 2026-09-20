from __future__ import annotations

import json

import typer

from modules.datasource.adaptors import AdapterType
from modules.datasource.pipeline import StockInfoPipeline

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


@app.command()
def main(
    adapter: AdapterType = typer.Option(
        "akshare", "--adapter", help="选择数据源 adapter"
    ),
) -> None:
    from modules.app import App

    runtime = App()
    pipeline = StockInfoPipeline(runtime.database)
    result = pipeline.run(adapter, sync_mode="full")
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
