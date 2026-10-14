from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import polars as pl

from modules.backtest.engine import BacktestEngine, _ScheduledOrder
from modules.backtest.execution import OrderExecutor
from modules.backtest.market_data import DailyBarLookup
from modules.backtest.models import (
    BacktestConfig,
    BacktestResult,
    PortfolioPosition,
    PortfolioState,
)
from modules.backtest.order_builder import RebalanceOrderBuilder
from modules.backtest.result_recorder import ResultRecorder
from modules.backtest.trade_ledger import TradeLedger
from modules.backtest.valuation import PortfolioValuator
from modules.core.context import Context
from modules.datasource.service.stock_daily_service import StockDailyService
from modules.strategies.models import StrategyDecision, StrategyMeta, TargetPosition


class _AlwaysLongStrategy:
    def __init__(self) -> None:
        self.meta = StrategyMeta(id=1, name="always_long", lookback_days=0)

    def decide(
        self,
        context: Context,
        portfolio_state: PortfolioState,
    ) -> StrategyDecision:
        _ = context
        _ = portfolio_state
        return StrategyDecision(
            as_of_date="2024-01-02",
            targets=[TargetPosition(instrument_id="000001.SZ", target_weight=1.0)],
            close_missing_positions=True,
        )


class _OpenThenCloseStrategy:
    def __init__(self) -> None:
        self.meta = StrategyMeta(id=2, name="open_then_close", lookback_days=0)

    def decide(
        self,
        context: Context,
        portfolio_state: PortfolioState,
    ) -> StrategyDecision:
        _ = portfolio_state
        targets = []
        if context.end_date == "2024-01-02":
            targets = [TargetPosition(instrument_id="000001.SZ", target_weight=1.0)]
        return StrategyDecision(
            as_of_date=context.end_date,
            targets=targets,
            close_missing_positions=True,
        )


class BacktestEngineBuildContextTest(unittest.TestCase):
    @patch.object(StockDailyService, "load_stock_daily")
    @patch.object(BacktestEngine, "list_recent_trade_dates")
    def test_build_context_treats_lookback_days_as_inclusive_trade_day_count(
        self,
        mock_list_recent_trade_dates,
        mock_load_stock_daily,
    ) -> None:
        mock_list_recent_trade_dates.return_value = [
            "2024-02-01",
            "2024-02-02",
            "2024-02-05",
        ]
        mock_load_stock_daily.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 2, 1), date(2024, 2, 5)],
                "instrument_id": ["000001.SZ", "000001.SZ"],
                "close": [10.0, 11.0],
            }
        )

        engine = BacktestEngine(database=object())

        context = engine.build_context(
            as_of_date="2024-02-05",
            lookback_days=3,
            instruments=["000001.SZ"],
        )

        mock_list_recent_trade_dates.assert_called_once_with(
            end_date="2024-02-05",
            limit=3,
        )
        self.assertEqual(context.start_date, "2024-02-01")
        self.assertEqual(context.end_date, "2024-02-05")
        self.assertEqual(len(context.stock_daily_data), 1)
        self.assertEqual(context.stock_daily_data[0].instrument_id, "000001.SZ")
        _, kwargs = mock_load_stock_daily.call_args
        self.assertEqual(kwargs["start_date"], date(2024, 2, 1))
        self.assertEqual(kwargs["end_date"], date(2024, 2, 5))
        self.assertEqual(kwargs["instruments"], ["000001.SZ"])

    @patch.object(StockDailyService, "load_stock_daily")
    @patch.object(BacktestEngine, "list_recent_trade_dates")
    def test_build_context_includes_as_of_date_when_lookback_days_is_zero(
        self,
        mock_list_recent_trade_dates,
        mock_load_stock_daily,
    ) -> None:
        mock_list_recent_trade_dates.return_value = ["2024-02-05"]
        mock_load_stock_daily.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 2, 5)],
                "instrument_id": ["000001.SZ"],
                "close": [11.0],
            }
        )

        engine = BacktestEngine(database=object())

        context = engine.build_context(
            as_of_date="2024-02-05",
            lookback_days=0,
            instruments=["000001.SZ"],
        )

        mock_list_recent_trade_dates.assert_called_once_with(
            end_date="2024-02-05",
            limit=1,
        )
        self.assertEqual(context.start_date, "2024-02-05")
        self.assertEqual(context.end_date, "2024-02-05")


class BacktestEngineRunTest(unittest.TestCase):
    @patch.object(BacktestEngine, "build_context")
    @patch.object(BacktestEngine, "_load_market_data")
    @patch.object(BacktestEngine, "list_trade_dates")
    def test_run_executes_rebalance_at_next_open_with_board_lot_and_t_plus_one(
        self,
        mock_list_trade_dates,
        mock_load_market_data,
        mock_build_context,
    ) -> None:
        mock_list_trade_dates.return_value = [
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
        ]
        mock_load_market_data.return_value = pl.DataFrame(
            {
                "trade_date": [
                    date(2024, 1, 2),
                    date(2024, 1, 3),
                    date(2024, 1, 4),
                ],
                "instrument_id": ["000001.SZ", "000001.SZ", "000001.SZ"],
                "open": [10.0, 10.0, 12.0],
                "high": [10.0, 11.0, 12.0],
                "low": [10.0, 10.0, 12.0],
                "close": [10.0, 11.0, 12.0],
            }
        )
        mock_build_context.return_value = Context(
            start_date="2024-01-02",
            end_date="2024-01-02",
        )

        engine = BacktestEngine(database=object())
        strategy = _AlwaysLongStrategy()
        config = BacktestConfig(
            start_date="2024-01-02",
            end_date="2024-01-04",
            initial_cash=1500.0,
            rebalance_frequency="daily",
            commission_rate=0.0,
            slippage_rate=0.0,
            instruments=["000001.SZ"],
        )

        result = engine.run(strategy, config)

        self.assertEqual(result.trade_dates, ["2024-01-02", "2024-01-03", "2024-01-04"])
        self.assertEqual(
            result.rebalance_dates, ["2024-01-02", "2024-01-03", "2024-01-04"]
        )
        self.assertEqual(
            [point.total_equity for point in result.equity_curve],
            [1500.0, 1600.0, 1700.0],
        )
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.orders[0].side, "buy")
        self.assertEqual(result.orders[0].trade_date, "2024-01-03")
        self.assertEqual(result.orders[0].quantity, 100)
        self.assertAlmostEqual(result.final_portfolio_state.cash, 500.0)
        self.assertEqual(
            result.final_portfolio_state.positions["000001.SZ"].quantity, 100
        )
        self.assertEqual(
            result.final_portfolio_state.positions["000001.SZ"].available_quantity, 100
        )
        self.assertAlmostEqual(result.summary.final_equity, 1700.0)
        self.assertAlmostEqual(result.summary.total_return, 200.0 / 1500.0)
        self.assertGreater(result.summary.annualized_return, 0.0)
        self.assertGreater(result.summary.volatility, 0.0)
        self.assertAlmostEqual(result.summary.turnover_rate, (1000.0 / 1500.0) / 3.0)
        self.assertAlmostEqual(
            result.metadata["cumulative_turnover_multiple"],
            1000.0 / 1500.0,
        )
        self.assertEqual(
            result.metadata["turnover_rate_definition"],
            "average_daily_gross_turnover_over_previous_equity",
        )
        self.assertEqual(mock_build_context.call_count, 2)

        positions_by_date = {
            snapshot.trade_date: snapshot
            for snapshot in result.positions
            if snapshot.instrument_id == "000001.SZ"
        }
        self.assertEqual(positions_by_date["2024-01-03"].available_quantity, 0)
        self.assertEqual(positions_by_date["2024-01-04"].available_quantity, 100)

    @patch.object(BacktestEngine, "build_context")
    @patch.object(BacktestEngine, "_load_market_data")
    @patch.object(BacktestEngine, "list_trade_dates")
    def test_run_records_rejected_order_when_next_open_missing_during_execution(
        self,
        mock_list_trade_dates,
        mock_load_market_data,
        mock_build_context,
    ) -> None:
        mock_list_trade_dates.return_value = [
            "2024-01-02",
            "2024-01-03",
        ]
        mock_load_market_data.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                "instrument_id": ["000001.SZ", "000001.SZ"],
                "open": [10.0, None],
                "high": [10.0, 11.0],
                "low": [10.0, 9.0],
                "close": [10.0, 10.5],
            }
        )
        mock_build_context.return_value = Context(
            start_date="2024-01-02",
            end_date="2024-01-02",
        )

        engine = BacktestEngine(database=object())
        result = engine.run(
            _AlwaysLongStrategy(),
            BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-03",
                initial_cash=2000.0,
                rebalance_frequency="daily",
                commission_rate=0.0,
                slippage_rate=0.0,
                instruments=["000001.SZ"],
            ),
        )

        self.assertEqual(len(result.fills), 0)
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.orders[0].status, "rejected")
        self.assertEqual(result.orders[0].status_detail, "no_open_price")
        self.assertEqual(result.orders[0].quantity, 200)
        self.assertEqual(
            result.metadata["constraint_counts"]["skipped_no_price_orders"], 1
        )

    @patch.object(BacktestEngine, "build_context")
    @patch.object(BacktestEngine, "_load_market_data")
    @patch.object(BacktestEngine, "list_trade_dates")
    def test_run_blocks_buy_on_locked_limit_up_day(
        self,
        mock_list_trade_dates,
        mock_load_market_data,
        mock_build_context,
    ) -> None:
        mock_list_trade_dates.return_value = [
            "2024-01-02",
            "2024-01-03",
        ]
        mock_load_market_data.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                "instrument_id": ["000001.SZ", "000001.SZ"],
                "open": [10.0, 11.0],
                "high": [10.0, 11.0],
                "low": [10.0, 11.0],
                "close": [10.0, 11.0],
            }
        )
        mock_build_context.return_value = Context(
            start_date="2024-01-02",
            end_date="2024-01-02",
        )

        engine = BacktestEngine(database=object())
        strategy = _AlwaysLongStrategy()
        config = BacktestConfig(
            start_date="2024-01-02",
            end_date="2024-01-03",
            initial_cash=2000.0,
            rebalance_frequency="daily",
            commission_rate=0.0,
            slippage_rate=0.0,
            instruments=["000001.SZ"],
        )

        result = engine.run(strategy, config)

        self.assertEqual(len(result.orders), 1)
        self.assertEqual(len(result.fills), 0)
        self.assertEqual(result.orders[0].status, "rejected")
        self.assertEqual(result.orders[0].status_detail, "limit_blocked")
        self.assertEqual(
            [point.total_equity for point in result.equity_curve], [2000.0, 2000.0]
        )
        self.assertAlmostEqual(result.final_portfolio_state.cash, 2000.0)
        self.assertEqual(
            result.metadata["constraint_counts"]["limit_blocked_orders"], 1
        )
        self.assertEqual(mock_build_context.call_count, 1)

    @patch.object(BacktestEngine, "build_context")
    @patch.object(BacktestEngine, "_load_market_data")
    @patch.object(BacktestEngine, "list_trade_dates")
    def test_run_records_stale_price_valuation_when_close_missing(
        self,
        mock_list_trade_dates,
        mock_load_market_data,
        mock_build_context,
    ) -> None:
        mock_list_trade_dates.return_value = [
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
        ]
        mock_load_market_data.return_value = pl.DataFrame(
            {
                "trade_date": [
                    date(2024, 1, 2),
                    date(2024, 1, 3),
                    date(2024, 1, 4),
                ],
                "instrument_id": ["000001.SZ", "000001.SZ", "000001.SZ"],
                "open": [10.0, 10.0, 10.0],
                "high": [10.0, 10.0, 10.0],
                "low": [10.0, 10.0, 10.0],
                "close": [10.0, 10.0, None],
            }
        )
        mock_build_context.return_value = Context(
            start_date="2024-01-02",
            end_date="2024-01-02",
        )

        engine = BacktestEngine(database=object())
        result = engine.run(
            _AlwaysLongStrategy(),
            BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-04",
                initial_cash=1500.0,
                rebalance_frequency="daily",
                commission_rate=0.0,
                slippage_rate=0.0,
                instruments=["000001.SZ"],
            ),
        )

        self.assertEqual(result.metadata["stale_price_valuation_count"], 1)
        self.assertEqual(
            result.metadata["stale_price_valuation_dates"], {"2024-01-04": 1}
        )
        self.assertEqual(
            [point.total_equity for point in result.equity_curve],
            [1500.0, 1500.0, 1500.0],
        )

    @patch.object(BacktestEngine, "build_context")
    @patch.object(BacktestEngine, "_load_market_data")
    @patch.object(BacktestEngine, "list_trade_dates")
    def test_run_records_trade_record_after_round_trip_position(
        self,
        mock_list_trade_dates,
        mock_load_market_data,
        mock_build_context,
    ) -> None:
        mock_list_trade_dates.return_value = [
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
        ]
        mock_load_market_data.return_value = pl.DataFrame(
            {
                "trade_date": [
                    date(2024, 1, 2),
                    date(2024, 1, 3),
                    date(2024, 1, 4),
                ],
                "instrument_id": ["000001.SZ", "000001.SZ", "000001.SZ"],
                "open": [10.0, 10.0, 12.0],
                "high": [10.0, 10.0, 12.0],
                "low": [10.0, 10.0, 12.0],
                "close": [10.0, 10.0, 12.0],
            }
        )
        mock_build_context.side_effect = lambda *, as_of_date, **kwargs: Context(
            start_date=as_of_date,
            end_date=as_of_date,
        )

        engine = BacktestEngine(database=object())
        result = engine.run(
            _OpenThenCloseStrategy(),
            BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-04",
                initial_cash=2000.0,
                rebalance_frequency="daily",
                commission_rate=0.0,
                slippage_rate=0.0,
                instruments=["000001.SZ"],
            ),
        )

        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.summary.trade_count, 1)
        self.assertEqual(result.trades[0].instrument_id, "000001.SZ")
        self.assertEqual(result.trades[0].open_date, "2024-01-03")
        self.assertEqual(result.trades[0].close_date, "2024-01-04")
        self.assertEqual(result.trades[0].quantity, 200)
        self.assertAlmostEqual(result.trades[0].entry_price, 10.0)
        self.assertAlmostEqual(result.trades[0].exit_price, 12.0)
        self.assertAlmostEqual(result.trades[0].pnl, 400.0)
        self.assertAlmostEqual(result.trades[0].return_rate, 0.2)
        self.assertNotIn("000001.SZ", result.final_portfolio_state.positions)
        self.assertAlmostEqual(result.summary.final_equity, 2400.0)

    @patch.object(BacktestEngine, "build_context")
    @patch.object(BacktestEngine, "_load_market_data")
    @patch.object(BacktestEngine, "list_trade_dates")
    def test_run_records_rejected_order_when_target_below_board_lot(
        self,
        mock_list_trade_dates,
        mock_load_market_data,
        mock_build_context,
    ) -> None:
        mock_list_trade_dates.return_value = [
            "2024-01-02",
            "2024-01-03",
        ]
        mock_load_market_data.return_value = pl.DataFrame(
            {
                "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                "instrument_id": ["000001.SZ", "000001.SZ"],
                "open": [10.0, 10.0],
                "high": [10.0, 10.0],
                "low": [10.0, 10.0],
                "close": [10.0, 10.0],
            }
        )
        mock_build_context.return_value = Context(
            start_date="2024-01-02",
            end_date="2024-01-02",
        )

        engine = BacktestEngine(database=object())
        result = engine.run(
            _AlwaysLongStrategy(),
            BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-03",
                initial_cash=500.0,
                rebalance_frequency="daily",
                commission_rate=0.0,
                slippage_rate=0.0,
                instruments=["000001.SZ"],
            ),
        )

        self.assertEqual(len(result.fills), 0)
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.orders[0].status, "rejected")
        self.assertEqual(result.orders[0].status_detail, "below_board_lot")
        self.assertEqual(result.orders[0].quantity, 50)
        self.assertAlmostEqual(result.orders[0].requested_price or 0.0, 10.0)
        self.assertEqual(
            result.metadata["constraint_counts"]["below_board_lot_orders"], 1
        )


class BacktestExecutionComponentsTest(unittest.TestCase):
    def _bar_lookup(self, market_data: pl.DataFrame) -> DailyBarLookup:
        return DailyBarLookup.from_frame(market_data)

    def _build_rebalance_orders(
        self,
        *,
        decision: StrategyDecision,
        pricing_date: str,
        execution_date: str,
        portfolio_state: PortfolioState,
        bar_lookup: DailyBarLookup,
        result: BacktestResult,
    ) -> list[_ScheduledOrder]:
        builder = RebalanceOrderBuilder(
            bar_lookup=bar_lookup,
            recorder=ResultRecorder(result),
        )
        return builder.build(
            decision=decision,
            pricing_date=pricing_date,
            execution_date=execution_date,
            portfolio_state=portfolio_state,
        )

    def _execute_scheduled_orders(
        self,
        *,
        scheduled_orders: list[_ScheduledOrder],
        trade_date: str,
        portfolio_state: PortfolioState,
        open_trade_lots: dict,
        config: BacktestConfig,
        result: BacktestResult,
        bar_lookup: DailyBarLookup,
    ) -> float:
        recorder = ResultRecorder(result)
        ledger = TradeLedger(
            recorder=recorder,
            open_trade_lots=open_trade_lots,
        )
        executor = OrderExecutor(
            bar_lookup=bar_lookup,
            recorder=recorder,
            ledger=ledger,
            config=config,
        )
        return executor.execute_scheduled_orders(
            scheduled_orders=scheduled_orders,
            trade_date=trade_date,
            portfolio_state=portfolio_state,
        )

    def _builder(self) -> RebalanceOrderBuilder:
        result = BacktestResult.empty(
            config=BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-03",
            )
        )
        return RebalanceOrderBuilder(
            bar_lookup=DailyBarLookup({}),
            recorder=ResultRecorder(result),
        )

    def test_build_rebalance_orders_does_not_record_false_below_board_lot_buy_for_position_reduction(
        self,
    ) -> None:
        result = BacktestResult.empty(
            config=BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-03",
            )
        )
        portfolio_state = PortfolioState(
            cash=0.0,
            positions={
                "000001.SZ": PortfolioPosition(
                    instrument_id="000001.SZ",
                    quantity=100,
                    available_quantity=100,
                    average_cost=10.0,
                    last_price=10.0,
                    market_value=1000.0,
                )
            },
        )
        decision = StrategyDecision(
            as_of_date="2024-01-02",
            targets=[TargetPosition(instrument_id="000001.SZ", target_weight=0.2)],
            close_missing_positions=True,
        )
        bar_lookup = self._bar_lookup(
            pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 3)],
                    "instrument_id": ["000001.SZ"],
                    "open": [10.0],
                    "high": [10.0],
                    "low": [10.0],
                    "close": [10.0],
                }
            )
        )

        scheduled_orders = self._build_rebalance_orders(
            decision=decision,
            pricing_date="2024-01-03",
            execution_date="2024-01-03",
            portfolio_state=portfolio_state,
            bar_lookup=bar_lookup,
            result=result,
        )

        self.assertEqual(len(scheduled_orders), 1)
        self.assertEqual(scheduled_orders[0].side, "sell")
        self.assertEqual(scheduled_orders[0].quantity, 100)
        self.assertEqual(len(result.orders), 0)
        self.assertEqual(
            result.metadata.get("constraint_counts", {}).get(
                "below_board_lot_orders", 0
            ),
            0,
        )

    def test_execute_scheduled_orders_blocks_same_day_sell_by_t_plus_one(self) -> None:
        config = BacktestConfig(
            start_date="2024-01-03",
            end_date="2024-01-03",
            initial_cash=2000.0,
            commission_rate=0.0,
            slippage_rate=0.0,
        )
        portfolio_state = PortfolioState(cash=2000.0)
        result = BacktestResult.empty(config=config)
        bar_lookup = self._bar_lookup(
            pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "instrument_id": ["000001.SZ", "000001.SZ"],
                    "open": [10.0, 10.0],
                    "high": [10.0, 10.0],
                    "low": [10.0, 10.0],
                    "close": [10.0, 10.0],
                }
            )
        )
        scheduled_orders = [
            _ScheduledOrder(
                trade_date="2024-01-03",
                instrument_id="000001.SZ",
                side="buy",
                quantity=100,
                reason="buy_first",
            ),
            _ScheduledOrder(
                trade_date="2024-01-03",
                instrument_id="000001.SZ",
                side="sell",
                quantity=100,
                reason="sell_same_day",
            ),
        ]

        turnover_amount = self._execute_scheduled_orders(
            scheduled_orders=scheduled_orders,
            trade_date="2024-01-03",
            portfolio_state=portfolio_state,
            open_trade_lots={},
            config=config,
            result=result,
            bar_lookup=bar_lookup,
        )

        self.assertAlmostEqual(turnover_amount, 1000.0)
        self.assertEqual(len(result.orders), 2)
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.orders[0].side, "buy")
        self.assertEqual(result.orders[0].status, "filled")
        self.assertEqual(result.orders[1].side, "sell")
        self.assertEqual(result.orders[1].status, "rejected")
        self.assertEqual(result.orders[1].status_detail, "t_plus_one_blocked")
        self.assertEqual(portfolio_state.positions["000001.SZ"].quantity, 100)
        self.assertEqual(portfolio_state.positions["000001.SZ"].available_quantity, 0)
        self.assertEqual(
            result.metadata["constraint_counts"]["t_plus_one_blocked_orders"], 1
        )

    def test_execute_scheduled_orders_records_rejected_orders_for_no_price_and_limit_blocked(
        self,
    ) -> None:
        config = BacktestConfig(
            start_date="2024-01-03",
            end_date="2024-01-03",
            initial_cash=2000.0,
            commission_rate=0.0,
            slippage_rate=0.0,
        )
        portfolio_state = PortfolioState(cash=2000.0)
        result = BacktestResult.empty(config=config)
        bar_lookup = self._bar_lookup(
            pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "instrument_id": ["000002.SZ", "000002.SZ"],
                    "open": [10.0, 11.0],
                    "high": [10.0, 11.0],
                    "low": [10.0, 11.0],
                    "close": [10.0, 11.0],
                }
            )
        )
        scheduled_orders = [
            _ScheduledOrder(
                trade_date="2024-01-03",
                instrument_id="000001.SZ",
                side="buy",
                quantity=100,
                reason="missing_price",
            ),
            _ScheduledOrder(
                trade_date="2024-01-03",
                instrument_id="000002.SZ",
                side="buy",
                quantity=100,
                reason="limit_up",
            ),
        ]

        turnover_amount = self._execute_scheduled_orders(
            scheduled_orders=scheduled_orders,
            trade_date="2024-01-03",
            portfolio_state=portfolio_state,
            open_trade_lots={},
            config=config,
            result=result,
            bar_lookup=bar_lookup,
        )

        self.assertAlmostEqual(turnover_amount, 0.0)
        self.assertEqual(len(result.orders), 2)
        self.assertEqual(len(result.fills), 0)
        orders_by_instrument = {order.instrument_id: order for order in result.orders}
        self.assertEqual(orders_by_instrument["000001.SZ"].status, "rejected")
        self.assertEqual(
            orders_by_instrument["000001.SZ"].status_detail, "no_open_price"
        )
        self.assertEqual(orders_by_instrument["000002.SZ"].status, "rejected")
        self.assertEqual(
            orders_by_instrument["000002.SZ"].status_detail, "limit_blocked"
        )
        self.assertEqual(
            result.metadata["constraint_counts"]["skipped_no_price_orders"], 1
        )
        self.assertEqual(
            result.metadata["constraint_counts"]["limit_blocked_orders"], 1
        )

    def test_execute_scheduled_orders_blocks_open_limit_up_without_intraday_lock(
        self,
    ) -> None:
        config = BacktestConfig(
            start_date="2024-01-03",
            end_date="2024-01-03",
            initial_cash=2000.0,
            commission_rate=0.0,
            slippage_rate=0.0,
        )
        portfolio_state = PortfolioState(cash=2000.0)
        result = BacktestResult.empty(config=config)
        bar_lookup = self._bar_lookup(
            pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "instrument_id": ["000001.SZ", "000001.SZ"],
                    "open": [10.0, 11.0],
                    "high": [10.0, 11.2],
                    "low": [10.0, 10.8],
                    "close": [10.0, 10.9],
                }
            )
        )
        scheduled_orders = [
            _ScheduledOrder(
                trade_date="2024-01-03",
                instrument_id="000001.SZ",
                side="buy",
                quantity=100,
                reason="open_limit_up",
            ),
        ]

        turnover_amount = self._execute_scheduled_orders(
            scheduled_orders=scheduled_orders,
            trade_date="2024-01-03",
            portfolio_state=portfolio_state,
            open_trade_lots={},
            config=config,
            result=result,
            bar_lookup=bar_lookup,
        )

        self.assertAlmostEqual(turnover_amount, 0.0)
        self.assertEqual(len(result.fills), 0)
        self.assertEqual(result.orders[0].status, "rejected")
        self.assertEqual(result.orders[0].status_detail, "limit_blocked")

    def test_execute_scheduled_orders_records_split_transaction_costs_in_trades(
        self,
    ) -> None:
        config = BacktestConfig(
            start_date="2024-01-03",
            end_date="2024-01-04",
            initial_cash=5000.0,
            commission_rate=0.001,
            minimum_commission=5.0,
            stamp_duty_rate=0.001,
            transfer_fee_rate=0.00002,
            slippage_rate=0.0,
        )
        portfolio_state = PortfolioState(cash=5000.0)
        result = BacktestResult.empty(config=config)
        open_trade_lots = {}
        bar_lookup = self._bar_lookup(
            pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 3), date(2024, 1, 4)],
                    "instrument_id": ["000001.SZ", "000001.SZ"],
                    "open": [10.0, 12.0],
                    "high": [10.0, 12.0],
                    "low": [10.0, 12.0],
                    "close": [10.0, 12.0],
                }
            )
        )

        self._execute_scheduled_orders(
            scheduled_orders=[
                _ScheduledOrder(
                    trade_date="2024-01-03",
                    instrument_id="000001.SZ",
                    side="buy",
                    quantity=100,
                    reason="open",
                )
            ],
            trade_date="2024-01-03",
            portfolio_state=portfolio_state,
            open_trade_lots=open_trade_lots,
            config=config,
            result=result,
            bar_lookup=bar_lookup,
        )
        PortfolioValuator(bar_lookup).roll_position_availability(portfolio_state)
        self._execute_scheduled_orders(
            scheduled_orders=[
                _ScheduledOrder(
                    trade_date="2024-01-04",
                    instrument_id="000001.SZ",
                    side="sell",
                    quantity=100,
                    reason="close",
                )
            ],
            trade_date="2024-01-04",
            portfolio_state=portfolio_state,
            open_trade_lots=open_trade_lots,
            config=config,
            result=result,
            bar_lookup=bar_lookup,
        )

        self.assertEqual(len(result.fills), 2)
        self.assertAlmostEqual(result.fills[0].commission, 5.0)
        self.assertAlmostEqual(result.fills[0].stamp_duty, 0.0)
        self.assertAlmostEqual(result.fills[0].transfer_fee, 0.02)
        self.assertAlmostEqual(result.fills[1].commission, 5.0)
        self.assertAlmostEqual(result.fills[1].stamp_duty, 1.2)
        self.assertAlmostEqual(result.fills[1].transfer_fee, 0.024)
        self.assertEqual(len(result.trades), 1)
        self.assertAlmostEqual(result.trades[0].pnl, 188.756)
        self.assertAlmostEqual(portfolio_state.cash, 5188.756)

    def test_execute_scheduled_orders_allocates_cash_across_buy_block_and_marks_partial_fill(
        self,
    ) -> None:
        config = BacktestConfig(
            start_date="2024-01-03",
            end_date="2024-01-03",
            initial_cash=2000.0,
            commission_rate=0.0,
            slippage_rate=0.0,
        )
        portfolio_state = PortfolioState(cash=2000.0)
        result = BacktestResult.empty(config=config)
        bar_lookup = self._bar_lookup(
            pl.DataFrame(
                {
                    "trade_date": [
                        date(2024, 1, 2),
                        date(2024, 1, 3),
                        date(2024, 1, 2),
                        date(2024, 1, 3),
                    ],
                    "instrument_id": [
                        "000001.SZ",
                        "000001.SZ",
                        "000002.SZ",
                        "000002.SZ",
                    ],
                    "open": [10.0, 10.0, 10.0, 10.0],
                    "high": [10.0, 10.0, 10.0, 10.0],
                    "low": [10.0, 10.0, 10.0, 10.0],
                    "close": [10.0, 10.0, 10.0, 10.0],
                }
            )
        )
        scheduled_orders = [
            _ScheduledOrder(
                trade_date="2024-01-03",
                instrument_id="000001.SZ",
                side="buy",
                quantity=200,
                reason="target_a",
            ),
            _ScheduledOrder(
                trade_date="2024-01-03",
                instrument_id="000002.SZ",
                side="buy",
                quantity=100,
                reason="target_b",
            ),
        ]

        turnover_amount = self._execute_scheduled_orders(
            scheduled_orders=scheduled_orders,
            trade_date="2024-01-03",
            portfolio_state=portfolio_state,
            open_trade_lots={},
            config=config,
            result=result,
            bar_lookup=bar_lookup,
        )

        self.assertAlmostEqual(turnover_amount, 2000.0)
        self.assertAlmostEqual(portfolio_state.cash, 0.0)
        self.assertEqual(portfolio_state.positions["000001.SZ"].quantity, 100)
        self.assertEqual(portfolio_state.positions["000002.SZ"].quantity, 100)
        self.assertEqual(len(result.orders), 2)
        self.assertEqual(len(result.fills), 2)
        orders_by_instrument = {order.instrument_id: order for order in result.orders}
        fills_by_instrument = {fill.instrument_id: fill for fill in result.fills}
        self.assertEqual(orders_by_instrument["000001.SZ"].status, "partially_filled")
        self.assertEqual(orders_by_instrument["000001.SZ"].quantity, 200)
        self.assertEqual(fills_by_instrument["000001.SZ"].quantity, 100)
        self.assertEqual(orders_by_instrument["000002.SZ"].status, "filled")
        self.assertEqual(orders_by_instrument["000002.SZ"].quantity, 100)
        self.assertEqual(fills_by_instrument["000002.SZ"].quantity, 100)
        self.assertEqual(
            result.metadata["constraint_counts"]["insufficient_cash_orders"], 1
        )

    def test_build_rebalance_orders_does_not_require_execution_open_price(
        self,
    ) -> None:
        result = BacktestResult.empty(
            config=BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-03",
            )
        )
        portfolio_state = PortfolioState(cash=1000.0)
        decision = StrategyDecision(
            as_of_date="2024-01-02",
            targets=[TargetPosition(instrument_id="000001.SZ", target_weight=1.0)],
            close_missing_positions=True,
        )
        bar_lookup = self._bar_lookup(
            pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "instrument_id": ["000001.SZ", "000001.SZ"],
                    "open": [10.0, None],
                    "high": [10.0, 20.0],
                    "low": [10.0, 20.0],
                    "close": [10.0, 20.0],
                }
            )
        )

        scheduled_orders = self._build_rebalance_orders(
            decision=decision,
            pricing_date="2024-01-02",
            execution_date="2024-01-03",
            portfolio_state=portfolio_state,
            bar_lookup=bar_lookup,
            result=result,
        )

        self.assertEqual(len(scheduled_orders), 1)
        self.assertEqual(scheduled_orders[0].side, "buy")
        self.assertEqual(scheduled_orders[0].quantity, 100)
        self.assertIsNone(scheduled_orders[0].requested_price)
        self.assertEqual(len(result.orders), 0)

    def test_build_rebalance_orders_treats_zero_weight_as_explicit_close(
        self,
    ) -> None:
        result = BacktestResult.empty(
            config=BacktestConfig(
                start_date="2024-01-02",
                end_date="2024-01-03",
            )
        )
        portfolio_state = PortfolioState(
            cash=0.0,
            positions={
                "000001.SZ": PortfolioPosition(
                    instrument_id="000001.SZ",
                    quantity=100,
                    available_quantity=100,
                    average_cost=10.0,
                    last_price=10.0,
                    market_value=1000.0,
                ),
                "000002.SZ": PortfolioPosition(
                    instrument_id="000002.SZ",
                    quantity=100,
                    available_quantity=100,
                    average_cost=10.0,
                    last_price=10.0,
                    market_value=1000.0,
                ),
            },
        )
        decision = StrategyDecision(
            as_of_date="2024-01-02",
            targets=[TargetPosition(instrument_id="000001.SZ", target_weight=0.0)],
            close_missing_positions=False,
        )
        bar_lookup = self._bar_lookup(
            pl.DataFrame(
                {
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "instrument_id": ["000001.SZ", "000001.SZ"],
                    "open": [10.0, 10.0],
                    "high": [10.0, 10.0],
                    "low": [10.0, 10.0],
                    "close": [10.0, 10.0],
                }
            )
        )

        scheduled_orders = self._build_rebalance_orders(
            decision=decision,
            pricing_date="2024-01-02",
            execution_date="2024-01-03",
            portfolio_state=portfolio_state,
            bar_lookup=bar_lookup,
            result=result,
        )

        self.assertEqual(len(scheduled_orders), 1)
        self.assertEqual(scheduled_orders[0].instrument_id, "000001.SZ")
        self.assertEqual(scheduled_orders[0].side, "sell")
        self.assertEqual(scheduled_orders[0].quantity, 100)

    def test_normalize_targets_rejects_duplicate_instrument(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate target instrument_id"):
            self._builder().normalize_targets(
                [
                    TargetPosition(instrument_id="000001.SZ", target_weight=0.3),
                    TargetPosition(instrument_id="000001.SZ", target_weight=0.2),
                ]
            )

    def test_normalize_targets_rejects_negative_weight(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "target_weight must be non-negative"):
            self._builder().normalize_targets(
                [TargetPosition(instrument_id="000001.SZ", target_weight=-0.1)]
            )

    def test_normalize_targets_rejects_total_weight_above_one(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "total target_weight"):
            self._builder().normalize_targets(
                [
                    TargetPosition(instrument_id="000001.SZ", target_weight=0.6),
                    TargetPosition(instrument_id="000002.SZ", target_weight=0.5),
                ]
            )


if __name__ == "__main__":
    unittest.main()
