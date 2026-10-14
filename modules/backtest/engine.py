from __future__ import annotations

import polars as pl

from modules.backtest.analyzer import BacktestAnalyzer
from modules.backtest.execution import OrderExecutor
from modules.backtest.market_data import DailyBarLookup
from modules.backtest.models import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    PortfolioState,
)
from modules.backtest.order_builder import RebalanceOrderBuilder
from modules.backtest.orders import ScheduledOrder as _ScheduledOrder
from modules.backtest.result_recorder import ResultRecorder
from modules.backtest.rules import (
    BOARD_LOT_SIZE,
    DEFAULT_MARKET_RULES,
    LIMIT_MOVE_THRESHOLD,
    MarketRules,
    SAME_PRICE_TOLERANCE,
)
from modules.backtest.scheduler import RebalanceScheduler
from modules.backtest.trade_ledger import TradeLedger
from modules.backtest.valuation import PortfolioValuator
from modules.core.context import Context, StockDailyData
from modules.datasource.service.stock_daily_service import StockDailyService
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.strategies.base import BaseStrategy
from modules.utils.time_util import format_date, parse_date


class BacktestEngine:
    """回测引擎入口，负责组装协作对象并推进逐日回测流程。"""

    BOARD_LOT_SIZE = BOARD_LOT_SIZE
    LIMIT_MOVE_THRESHOLD = LIMIT_MOVE_THRESHOLD
    SAME_PRICE_TOLERANCE = SAME_PRICE_TOLERANCE

    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        scheduler: RebalanceScheduler | None = None,
        analyzer: BacktestAnalyzer | None = None,
        rules: MarketRules = DEFAULT_MARKET_RULES,
    ) -> None:
        """绑定数据源、调仓调度器、分析器和市场规则。"""
        self._database = database
        self._stock_daily_service = StockDailyService(database)
        self._scheduler = scheduler or RebalanceScheduler()
        self._analyzer = analyzer or BacktestAnalyzer()
        self._rules = rules

    def prepare_result_skeleton(self, config: BacktestConfig) -> BacktestResult:
        """校验配置，并根据交易日历生成空的回测结果骨架。"""
        self._validate_config(config)
        trade_dates = self.list_trade_dates(config.start_date, config.end_date)
        rebalance_dates = self._scheduler.build_rebalance_dates(
            trade_dates,
            config.rebalance_frequency,
        )
        return BacktestResult.empty(
            config=config,
            trade_dates=trade_dates,
            rebalance_dates=rebalance_dates,
        )

    def run(
        self,
        strategy: "BaseStrategy",
        config: BacktestConfig,
    ) -> BacktestResult:
        """运行完整回测，按调仓日决策、下一交易日开盘执行、收盘估值。"""
        result = self.prepare_result_skeleton(config)
        if not result.trade_dates:
            return result

        market_data = self._load_market_data(config)
        bar_lookup = DailyBarLookup.from_frame(market_data, rules=self._rules)
        recorder = ResultRecorder(result)
        trade_ledger = TradeLedger(recorder=recorder)
        order_builder = RebalanceOrderBuilder(
            bar_lookup=bar_lookup,
            recorder=recorder,
            rules=self._rules,
        )
        order_executor = OrderExecutor(
            bar_lookup=bar_lookup,
            recorder=recorder,
            ledger=trade_ledger,
            config=config,
            rules=self._rules,
        )
        valuator = PortfolioValuator(bar_lookup)
        next_trade_date_map = self._build_next_trade_date_map(result.trade_dates)
        portfolio_state = self.create_initial_portfolio_state(config)
        pending_orders: dict[str, list[_ScheduledOrder]] = {}
        turnover_amount = 0.0
        result.metadata["constraint_counts"] = {
            "skipped_no_price_orders": 0,
            "t_plus_one_blocked_orders": 0,
            "limit_blocked_orders": 0,
            "insufficient_cash_orders": 0,
            "below_board_lot_orders": 0,
        }
        result.metadata["stale_price_valuation_count"] = 0
        result.metadata["stale_price_valuation_dates"] = {}

        for trade_date in result.trade_dates:
            valuator.roll_position_availability(portfolio_state)
            scheduled_orders = pending_orders.pop(trade_date, [])
            turnover_amount += order_executor.execute_scheduled_orders(
                scheduled_orders=scheduled_orders,
                trade_date=trade_date,
                portfolio_state=portfolio_state,
            )
            stale_price_count = valuator.mark_to_market(
                trade_date=trade_date,
                portfolio_state=portfolio_state,
            )
            if stale_price_count > 0:
                result.metadata["stale_price_valuation_count"] += stale_price_count
                result.metadata["stale_price_valuation_dates"][
                    trade_date
                ] = stale_price_count
            result.equity_curve.append(
                EquityPoint(
                    trade_date=trade_date,
                    cash=float(portfolio_state.cash),
                    market_value=float(portfolio_state.total_market_value),
                    total_equity=float(portfolio_state.total_equity),
                )
            )
            result.positions.extend(
                valuator.build_position_snapshots(
                    trade_date=trade_date,
                    portfolio_state=portfolio_state,
                )
            )

            next_trade_date = next_trade_date_map.get(trade_date)
            if trade_date not in result.rebalance_dates or next_trade_date is None:
                continue

            context = self.build_context(
                as_of_date=trade_date,
                lookback_days=max(0, int(strategy.meta.lookback_days)),
                instruments=config.instruments or None,
                optional=config.optional,
                data_columns=config.data_columns or None,
            )
            decision = strategy.decide(context, portfolio_state)
            scheduled_orders = order_builder.build(
                decision=decision,
                pricing_date=trade_date,
                execution_date=next_trade_date,
                portfolio_state=portfolio_state,
            )
            if scheduled_orders:
                pending_orders.setdefault(next_trade_date, []).extend(scheduled_orders)
            result.metadata.setdefault("decisions", {})[trade_date] = {
                "as_of_date": decision.as_of_date,
                "target_count": len(decision.targets),
                "execution_date": next_trade_date,
            }

        cumulative_turnover_multiple = (
            float(turnover_amount / config.initial_cash)
            if config.initial_cash > 0
            else 0.0
        )
        result.final_portfolio_state = valuator.copy_portfolio_state(portfolio_state)
        result.summary = self._analyzer.build_summary(result)
        result.metadata.update(
            {
                "execution_model": "next_open",
                "trade_date_count": len(result.trade_dates),
                "rebalance_date_count": len(result.rebalance_dates),
                "board_lot_size": self.BOARD_LOT_SIZE,
                "turnover_rate_definition": "average_daily_gross_turnover_over_previous_equity",
                "cumulative_turnover_multiple": cumulative_turnover_multiple,
                "transaction_cost_model": {
                    "commission_rate": float(config.commission_rate),
                    "minimum_commission": float(config.minimum_commission),
                    "stamp_duty_rate": float(config.stamp_duty_rate),
                    "transfer_fee_rate": float(config.transfer_fee_rate),
                },
                "unexecuted_scheduled_order_count": sum(
                    len(orders) for orders in pending_orders.values()
                ),
            }
        )
        return result

    def list_trade_dates(self, start_date: str, end_date: str) -> list[str]:
        """读取指定区间内的开市交易日。"""
        with RepositorySession(self._database) as session:
            return session.trading_calendar.list_open_trade_dates(
                start_date=start_date,
                end_date=end_date,
            )

    def list_recent_trade_dates(self, end_date: str, limit: int) -> list[str]:
        """读取截止某日最近的开市交易日，用于构造策略上下文。"""
        if limit <= 0:
            return []
        with RepositorySession(self._database) as session:
            return session.trading_calendar.list_recent_open_trade_dates(
                end_date=end_date,
                limit=limit,
            )

    def create_initial_portfolio_state(self, config: BacktestConfig) -> PortfolioState:
        """根据初始资金创建回测起始组合状态。"""
        return PortfolioState(
            cash=float(config.initial_cash),
            frozen_cash=0.0,
        )

    def build_context(
        self,
        *,
        as_of_date: str,
        lookback_days: int,
        instruments: list[str] | None = None,
        optional: bool = False,
        data_columns: list[str] | None = None,
    ) -> Context:
        """构造策略在指定日期可见的历史行情上下文。"""
        end_date = parse_date(as_of_date)
        if end_date is None:
            raise ValueError(f"invalid as_of_date: {as_of_date}")
        # lookback_days 当前约定为“上下文中包含的交易日样本数”，包含 as_of_date 当天。
        recent_trade_dates = self.list_recent_trade_dates(
            end_date=as_of_date,
            limit=max(1, lookback_days),
        )
        start_date = (
            parse_date(recent_trade_dates[0]) if recent_trade_dates else end_date
        )
        columns = data_columns or None
        frame = self._stock_daily_service.load_stock_daily(
            start_date=start_date,
            end_date=end_date,
            instruments=instruments,
            columns=columns,
            optional=optional,
        )
        return Context(
            start_date=format_date(start_date) or as_of_date,
            end_date=format_date(end_date) or as_of_date,
            stock_daily_data=self._group_stock_daily_data(frame),
        )

    def _load_market_data(self, config: BacktestConfig) -> pl.DataFrame:
        """加载回测执行所需的 OHLC 行情。"""
        requested_columns = ["open", "high", "low", "close"]
        return self._stock_daily_service.load_stock_daily(
            start_date=parse_date(config.start_date),
            end_date=parse_date(config.end_date),
            instruments=config.instruments or None,
            columns=requested_columns,
            optional=config.optional,
        )

    @classmethod
    def _validate_config(cls, config: BacktestConfig) -> None:
        """校验回测配置中的日期、资金、费用和调仓频率。"""
        start_date = parse_date(config.start_date)
        end_date = parse_date(config.end_date)
        if start_date is None or end_date is None:
            raise ValueError("start_date and end_date must be valid dates")
        if start_date > end_date:
            raise ValueError("start_date must be earlier than or equal to end_date")
        if config.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if (
            config.commission_rate < 0
            or config.minimum_commission < 0
            or config.stamp_duty_rate < 0
            or config.transfer_fee_rate < 0
            or config.slippage_rate < 0
        ):
            raise ValueError("transaction cost rates must be non-negative")
        if config.rebalance_frequency not in RebalanceScheduler.SUPPORTED_FREQUENCIES:
            raise ValueError(
                f"unsupported rebalance frequency: {config.rebalance_frequency}"
            )

    @classmethod
    def _group_stock_daily_data(cls, data: pl.DataFrame) -> list[StockDailyData]:
        """把按行存储的日线数据分组成 Context 需要的标的序列。"""
        if data.is_empty():
            return []
        grouped_data = data.sort(["instrument_id", "trade_date"]).partition_by(
            "instrument_id",
            maintain_order=True,
        )
        return [
            StockDailyData(
                instrument_id=str(group["instrument_id"][0]),
                data=group,
            )
            for group in grouped_data
        ]

    @classmethod
    def _build_next_trade_date_map(cls, trade_dates: list[str]) -> dict[str, str]:
        """构造当前交易日到下一交易日的映射，用于 next_open 执行。"""
        return {
            current_date: next_date
            for current_date, next_date in zip(trade_dates, trade_dates[1:])
        }
