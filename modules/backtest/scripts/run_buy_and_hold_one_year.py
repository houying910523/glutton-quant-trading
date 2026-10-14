from __future__ import annotations

import json
from dataclasses import asdict

from modules.backtest.analyzer import BacktestAnalyzer
from modules.backtest.engine import BacktestEngine
from modules.backtest.models import BacktestConfig, BacktestResult
from modules.repositories.database import SQLiteDatabase
from modules.strategies.buy_and_hold_strategy import BuyAndHoldStrategy


INSTRUMENTS = [
    "000001.SZ",
    "000002.SZ",
    "600036.SH",
    "600519.SH",
    "601318.SH",
]


def main() -> None:
    """使用真实 SQLite 日线数据跑一年 5 股票等权策略回测。"""
    database = SQLiteDatabase()
    engine = BacktestEngine(database)
    analyzer = BacktestAnalyzer()
    strategy = BuyAndHoldStrategy(instrument_ids=INSTRUMENTS)
    config = BacktestConfig(
        start_date="2025-10-01",
        end_date="2026-09-30",
        initial_cash=1_000_000.0,
        rebalance_frequency="monthly",
        instruments=INSTRUMENTS,
    )

    result = engine.run(strategy, config)
    analysis = analyzer.analyze(result)

    print("=== Backtest Result ===")
    print(
        json.dumps(
            _build_result_payload(result),
            ensure_ascii=False,
            indent=2,
        )
    )
    print("=== Analyzer Result ===")
    print(
        json.dumps(
            asdict(analysis),
            ensure_ascii=False,
            indent=2,
        )
    )


def _build_result_payload(result: BacktestResult) -> dict[str, object]:
    """提取终局回测结果，避免直接打印过长的逐日明细。"""
    return {
        "config": asdict(result.config),
        "trade_date_count": len(result.trade_dates),
        "rebalance_dates": result.rebalance_dates,
        "summary": asdict(result.summary),
        "final_portfolio_state": asdict(result.final_portfolio_state),
        "order_count": len(result.orders),
        "fill_count": len(result.fills),
        "trade_count": len(result.trades),
        "last_5_equity_points": [asdict(point) for point in result.equity_curve[-5:]],
        "last_5_position_snapshots": [
            asdict(snapshot) for snapshot in result.positions[-5:]
        ],
        "metadata": result.metadata,
    }


if __name__ == "__main__":
    main()
