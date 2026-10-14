from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BacktestConfig:
    """回测运行配置。"""

    start_date: str  # 回测起始日期，格式 YYYY-MM-DD。
    end_date: str  # 回测结束日期，格式 YYYY-MM-DD。
    initial_cash: float = 1_000_000.0  # 初始资金。
    rebalance_frequency: str = "monthly"  # 调仓频率，如 daily / weekly / monthly。
    # benchmark: str | None = None  # 基准代码，等基准分析实现后再启用。
    commission_rate: float = 0.0003  # 手续费率。
    minimum_commission: float = 0.0  # 单笔最低手续费，0 表示不启用。
    stamp_duty_rate: float = 0.0  # 卖出侧印花税率。
    transfer_fee_rate: float = 0.0  # 买卖双边过户费或其他按成交额计费的费率。
    slippage_rate: float = 0.0005  # 滑点率。
    # top_n: int | None = None  # 组合截断由具体策略负责，回测配置暂不启用。
    optional: bool = False  # 是否仅使用 optional 股票池。
    instruments: list[str] = field(default_factory=list)  # 限定参与回测的证券列表。
    data_columns: list[str] = field(
        default_factory=list
    )  # 构造策略上下文时附带的日线字段。
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外配置扩展字段。


@dataclass
class PortfolioPosition:
    """单个标的在组合中的持仓状态。"""

    instrument_id: str  # 证券标识，如 600519.SH。
    quantity: int = 0  # 当前总持仓数量。
    available_quantity: int = 0  # 当前可卖数量，受 T+1 等约束影响。
    average_cost: float = 0.0  # 持仓平均成本。
    last_price: float | None = None  # 最近一次用于估值的价格。
    market_value: float = 0.0  # 当前持仓市值。


@dataclass
class PortfolioState:
    """组合在某个交易时点的整体状态。"""

    as_of_date: str | None = None  # 当前组合状态对应的交易日。
    cash: float = 0.0  # 可用现金。
    frozen_cash: float = 0.0  # 冻结现金，当前主要预留给后续扩展。
    positions: dict[str, PortfolioPosition] = field(
        default_factory=dict
    )  # 按 instrument_id 索引的持仓明细。

    @property
    def total_market_value(self) -> float:
        """当前所有持仓的总市值。"""
        return sum(position.market_value for position in self.positions.values())

    @property
    def total_equity(self) -> float:
        """当前总权益 = 现金 + 冻结现金 + 持仓市值。"""
        return self.cash + self.frozen_cash + self.total_market_value


@dataclass(frozen=True)
class OrderIntent:
    """订单意图或已生成订单记录。"""

    order_id: str  # 订单唯一标识。
    trade_date: str  # 订单所属交易日。
    instrument_id: str  # 证券标识。
    side: str  # 方向，如 buy / sell。
    quantity: int  # 委托数量。
    requested_price: float | None = None  # 委托参考价格。
    status: str = "created"  # 订单状态。
    reason: str = ""  # 订单产生原因或备注。
    status_detail: str = ""  # 状态补充说明，如 no_open_price / limit_blocked。


@dataclass(frozen=True)
class FillRecord:
    """订单成交记录。"""

    fill_id: str  # 成交记录唯一标识。
    order_id: str  # 对应的订单 ID。
    trade_date: str  # 成交日期。
    instrument_id: str  # 证券标识。
    side: str  # 成交方向，如 buy / sell。
    quantity: int  # 成交数量。
    price: float  # 成交价格。
    commission: float = 0.0  # 手续费金额。
    stamp_duty: float = 0.0  # 印花税金额。
    transfer_fee: float = 0.0  # 过户费或其他按成交额计费的费用。
    slippage: float = 0.0  # 滑点金额。
    amount: float = 0.0  # 成交金额，不含手续费。


@dataclass(frozen=True)
class TradeRecord:
    """闭合交易记录。"""

    trade_id: str  # 交易记录唯一标识。
    instrument_id: str  # 证券标识。
    open_date: str  # 开仓日期。
    close_date: str  # 平仓日期。
    quantity: int  # 闭合交易数量。
    entry_price: float  # 开仓成交价。
    exit_price: float  # 平仓成交价。
    pnl: float  # 该笔闭合交易盈亏。
    return_rate: float  # 该笔闭合交易收益率。


@dataclass(frozen=True)
class EquityPoint:
    """某个交易日的权益曲线点。"""

    trade_date: str  # 交易日。
    cash: float  # 当日收盘后现金。
    market_value: float  # 当日收盘后持仓总市值。
    total_equity: float  # 当日总权益。


@dataclass(frozen=True)
class PositionSnapshot:
    """某个交易日收盘后的持仓快照。"""

    trade_date: str  # 交易日。
    instrument_id: str  # 证券标识。
    quantity: int  # 总持仓数量。
    available_quantity: int  # 可卖数量。
    average_cost: float  # 平均持仓成本。
    close_price: float | None  # 当日用于估值的收盘价。
    market_value: float  # 当日持仓市值。
    weight: float  # 该持仓占组合总权益的权重。


@dataclass(frozen=True)
class BacktestSummary:
    """回测摘要指标。"""

    initial_cash: float = 0.0  # 初始资金。
    final_equity: float = 0.0  # 回测结束时总权益。
    total_return: float = 0.0  # 总收益率。
    annualized_return: float = 0.0  # 年化收益率。
    max_drawdown: float = 0.0  # 最大回撤。
    volatility: float = 0.0  # 年化波动率。
    sharpe_ratio: float = 0.0  # 夏普比率。
    turnover_rate: float = 0.0  # 日均成交额 / 上日权益的近似换手率。
    order_count: int = 0  # 订单数。
    fill_count: int = 0  # 成交数。
    trade_count: int = 0  # 闭合交易数。


@dataclass(frozen=True)
class PeriodReturn:
    """某个周期的区间收益。"""

    period: str  # 周期标识，如 2024-01 或 2024。
    start_equity: float  # 周期起始权益。
    end_equity: float  # 周期结束权益。
    return_rate: float  # 周期收益率。


@dataclass
class BacktestResult:
    """回测执行结果。"""

    config: BacktestConfig  # 本次回测使用的配置。
    trade_dates: list[str] = field(default_factory=list)  # 回测区间内实际交易日列表。
    rebalance_dates: list[str] = field(
        default_factory=list
    )  # 触发调仓决策的交易日列表。
    summary: BacktestSummary = field(default_factory=BacktestSummary)  # 回测摘要结果。
    final_portfolio_state: PortfolioState = field(
        default_factory=PortfolioState
    )  # 回测结束时的组合状态。
    equity_curve: list[EquityPoint] = field(default_factory=list)  # 每日权益曲线。
    positions: list[PositionSnapshot] = field(
        default_factory=list
    )  # 每日持仓快照序列。
    orders: list[OrderIntent] = field(default_factory=list)  # 订单记录。
    fills: list[FillRecord] = field(default_factory=list)  # 成交记录。
    trades: list[TradeRecord] = field(default_factory=list)  # 闭合交易记录。
    metadata: dict[str, Any] = field(default_factory=dict)  # 回测过程中的扩展信息。

    @classmethod
    def empty(
        cls,
        *,
        config: BacktestConfig,
        trade_dates: list[str] | None = None,
        rebalance_dates: list[str] | None = None,
    ) -> "BacktestResult":
        """构造一个带初始资金状态的空回测结果。"""
        initial_state = PortfolioState(
            cash=float(config.initial_cash),
            frozen_cash=0.0,
        )
        return cls(
            config=config,
            trade_dates=trade_dates or [],
            rebalance_dates=rebalance_dates or [],
            summary=BacktestSummary(
                initial_cash=float(config.initial_cash),
                final_equity=float(config.initial_cash),
            ),
            final_portfolio_state=initial_state,
        )


@dataclass(frozen=True)
class BacktestAnalyzeResult:
    """回测分析结果。"""

    summary: BacktestSummary  # 汇总统计结果。
    monthly_returns: list[PeriodReturn] = field(default_factory=list)  # 月度收益序列。
    yearly_returns: list[PeriodReturn] = field(default_factory=list)  # 年度收益序列。
    max_drawdown_start_date: str | None = None  # 最大回撤起点日期。
    max_drawdown_end_date: str | None = None  # 最大回撤终点日期。
    metadata: dict[str, Any] = field(default_factory=dict)  # 分析阶段扩展信息。
