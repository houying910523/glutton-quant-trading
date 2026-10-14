from __future__ import annotations

import unittest

from modules.backtest.analyzer import BacktestAnalyzer
from modules.backtest.models import (
    BacktestConfig,
    BacktestResult,
    BacktestSummary,
    EquityPoint,
    FillRecord,
)


class BacktestAnalyzerBuildSummaryTest(unittest.TestCase):
    def test_analyze_recomputes_average_daily_turnover_rate(self) -> None:
        analyzer = BacktestAnalyzer()
        result = BacktestResult(
            config=BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-04",
                initial_cash=100.0,
            ),
            summary=BacktestSummary(turnover_rate=9.99),
            equity_curve=[
                EquityPoint(
                    trade_date="2024-01-02",
                    cash=100.0,
                    market_value=0.0,
                    total_equity=100.0,
                ),
                EquityPoint(
                    trade_date="2024-01-03",
                    cash=80.0,
                    market_value=20.0,
                    total_equity=100.0,
                ),
                EquityPoint(
                    trade_date="2024-01-04",
                    cash=80.0,
                    market_value=20.0,
                    total_equity=100.0,
                ),
            ],
            fills=[
                FillRecord(
                    fill_id="FIL-1",
                    order_id="ORD-1",
                    trade_date="2024-01-03",
                    instrument_id="000001.SZ",
                    side="buy",
                    quantity=2,
                    price=10.0,
                    amount=20.0,
                )
            ],
        )

        analyze_result = analyzer.analyze(result)

        self.assertAlmostEqual(
            analyze_result.summary.turnover_rate, (20.0 / 100.0) / 3.0
        )


class BacktestAnalyzerBuildPeriodReturnsTest(unittest.TestCase):
    def test_analyze_uses_previous_period_end_equity_for_monthly_and_yearly_returns(
        self,
    ) -> None:
        analyzer = BacktestAnalyzer()
        result = BacktestResult(
            config=BacktestConfig(
                start_date="2023-12-29",
                end_date="2024-02-29",
            ),
            equity_curve=[
                EquityPoint(
                    trade_date="2023-12-29",
                    cash=100.0,
                    market_value=0.0,
                    total_equity=100.0,
                ),
                EquityPoint(
                    trade_date="2024-01-02",
                    cash=120.0,
                    market_value=0.0,
                    total_equity=120.0,
                ),
                EquityPoint(
                    trade_date="2024-01-31",
                    cash=120.0,
                    market_value=0.0,
                    total_equity=120.0,
                ),
                EquityPoint(
                    trade_date="2024-02-01",
                    cash=132.0,
                    market_value=0.0,
                    total_equity=132.0,
                ),
                EquityPoint(
                    trade_date="2024-02-29",
                    cash=132.0,
                    market_value=0.0,
                    total_equity=132.0,
                ),
            ],
        )

        analyze_result = analyzer.analyze(result)

        monthly_returns = {item.period: item for item in analyze_result.monthly_returns}
        self.assertAlmostEqual(monthly_returns["2024-01"].start_equity, 100.0)
        self.assertAlmostEqual(monthly_returns["2024-01"].end_equity, 120.0)
        self.assertAlmostEqual(monthly_returns["2024-01"].return_rate, 0.2)
        self.assertAlmostEqual(monthly_returns["2024-02"].start_equity, 120.0)
        self.assertAlmostEqual(monthly_returns["2024-02"].end_equity, 132.0)
        self.assertAlmostEqual(monthly_returns["2024-02"].return_rate, 0.1)

        yearly_returns = {item.period: item for item in analyze_result.yearly_returns}
        self.assertAlmostEqual(yearly_returns["2024"].start_equity, 100.0)
        self.assertAlmostEqual(yearly_returns["2024"].end_equity, 132.0)
        self.assertAlmostEqual(yearly_returns["2024"].return_rate, 0.32)


if __name__ == "__main__":
    unittest.main()
