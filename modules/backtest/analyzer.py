from __future__ import annotations

import math
import statistics

from modules.backtest.models import (
    BacktestAnalyzeResult,
    BacktestResult,
    BacktestSummary,
    EquityPoint,
    FillRecord,
    PeriodReturn,
)


class BacktestAnalyzer:
    """从回测结果中计算收益、回撤、波动和周期收益。"""

    def analyze(self, backtest_result: BacktestResult) -> BacktestAnalyzeResult:
        """生成完整分析结果，包括摘要、周期收益和最大回撤区间。"""
        summary = self.build_summary(backtest_result)
        max_drawdown_start_date, max_drawdown_end_date = self._max_drawdown_window(
            backtest_result.equity_curve
        )
        return BacktestAnalyzeResult(
            summary=summary,
            monthly_returns=self._build_period_returns(
                backtest_result.equity_curve,
                period="monthly",
            ),
            yearly_returns=self._build_period_returns(
                backtest_result.equity_curve,
                period="yearly",
            ),
            max_drawdown_start_date=max_drawdown_start_date,
            max_drawdown_end_date=max_drawdown_end_date,
            metadata={
                "equity_points": len(backtest_result.equity_curve),
                "orders": len(backtest_result.orders),
                "fills": len(backtest_result.fills),
                "trades": len(backtest_result.trades),
            },
        )

    def build_summary(self, backtest_result: BacktestResult) -> BacktestSummary:
        """生成回测摘要指标，供引擎和独立分析入口复用。"""
        equity_curve = backtest_result.equity_curve
        initial_cash = float(backtest_result.config.initial_cash)
        turnover_rate = self._average_daily_turnover_rate(backtest_result)
        if not equity_curve:
            return BacktestSummary(
                initial_cash=initial_cash,
                final_equity=float(backtest_result.summary.final_equity),
                total_return=0.0,
                annualized_return=0.0,
                max_drawdown=0.0,
                volatility=0.0,
                sharpe_ratio=0.0,
                turnover_rate=turnover_rate,
                order_count=len(backtest_result.orders),
                fill_count=len(backtest_result.fills),
                trade_count=len(backtest_result.trades),
            )

        final_equity = equity_curve[-1].total_equity
        total_return = self._safe_return(initial_cash, final_equity)
        daily_returns = self._daily_returns(equity_curve)
        annualized_return = self._annualized_return(total_return, len(equity_curve))
        volatility = self._annualized_volatility(daily_returns)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0.0
        max_drawdown = self._max_drawdown(equity_curve)

        return BacktestSummary(
            initial_cash=initial_cash,
            final_equity=final_equity,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            turnover_rate=turnover_rate,
            order_count=len(backtest_result.orders),
            fill_count=len(backtest_result.fills),
            trade_count=len(backtest_result.trades),
        )

    def _build_daily_turnover_amounts(
        self,
        fills: list[FillRecord],
    ) -> dict[str, float]:
        """按成交日期汇总成交额，用于换手率计算。"""
        turnover_by_date: dict[str, float] = {}
        for fill in fills:
            turnover_by_date[fill.trade_date] = turnover_by_date.get(
                fill.trade_date, 0.0
            ) + float(fill.amount)
        return turnover_by_date

    def _average_daily_turnover_rate(self, backtest_result: BacktestResult) -> float:
        """计算以昨日权益为分母的平均日成交额换手率。"""
        equity_curve = backtest_result.equity_curve
        if not equity_curve:
            return 0.0
        turnover_by_date = self._build_daily_turnover_amounts(backtest_result.fills)
        previous_equity = float(backtest_result.config.initial_cash)
        accumulated_rate = 0.0
        for point in equity_curve:
            if previous_equity > 0:
                accumulated_rate += (
                    turnover_by_date.get(point.trade_date, 0.0) / previous_equity
                )
            previous_equity = float(point.total_equity)
        return accumulated_rate / len(equity_curve)

    def _daily_returns(self, equity_curve: list[EquityPoint]) -> list[float]:
        """由净值曲线推导相邻交易日收益率。"""
        returns: list[float] = []
        for previous, current in zip(equity_curve, equity_curve[1:]):
            if previous.total_equity <= 0:
                returns.append(0.0)
                continue
            returns.append(current.total_equity / previous.total_equity - 1.0)
        return returns

    def _annualized_return(self, total_return: float, observation_count: int) -> float:
        """按 252 个交易日假设把区间总收益年化。"""
        if observation_count <= 1:
            return 0.0
        base = 1.0 + total_return
        if base <= 0:
            return -1.0
        years = (observation_count - 1) / 252.0
        if years <= 0:
            return 0.0
        return math.pow(base, 1 / years) - 1.0

    def _annualized_volatility(self, daily_returns: list[float]) -> float:
        """按 252 个交易日假设把日收益波动年化。"""
        if len(daily_returns) < 2:
            return 0.0
        return statistics.pstdev(daily_returns) * math.sqrt(252.0)

    def _safe_return(self, start_value: float, end_value: float) -> float:
        """计算收益率；起始值无效时返回 0。"""
        if start_value <= 0:
            return 0.0
        return end_value / start_value - 1.0

    def _max_drawdown(self, equity_curve: list[EquityPoint]) -> float:
        """扫描净值曲线得到最大回撤比例。"""
        peak = 0.0
        max_drawdown = 0.0
        for point in equity_curve:
            if point.total_equity > peak:
                peak = point.total_equity
            if peak <= 0:
                continue
            drawdown = (peak - point.total_equity) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return max_drawdown

    def _max_drawdown_window(
        self,
        equity_curve: list[EquityPoint],
    ) -> tuple[str | None, str | None]:
        """扫描净值曲线得到最大回撤的起止日期。"""
        peak_value = 0.0
        peak_date: str | None = None
        max_drawdown = 0.0
        drawdown_start: str | None = None
        drawdown_end: str | None = None

        for point in equity_curve:
            if point.total_equity > peak_value:
                peak_value = point.total_equity
                peak_date = point.trade_date
            if peak_value <= 0:
                continue
            drawdown = (peak_value - point.total_equity) / peak_value
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                drawdown_start = peak_date
                drawdown_end = point.trade_date
        return drawdown_start, drawdown_end

    def _build_period_returns(
        self,
        equity_curve: list[EquityPoint],
        *,
        period: str,
    ) -> list[PeriodReturn]:
        """按月或年聚合净值曲线，生成周期收益。"""
        grouped: dict[str, list[EquityPoint]] = {}
        for point in equity_curve:
            if period == "monthly":
                key = point.trade_date[:7]
            elif period == "yearly":
                key = point.trade_date[:4]
            else:
                raise ValueError(f"unsupported period: {period}")
            grouped.setdefault(key, []).append(point)

        result: list[PeriodReturn] = []
        previous_end_equity: float | None = None
        for key, points in grouped.items():
            start_equity = (
                previous_end_equity
                if previous_end_equity is not None
                else points[0].total_equity
            )
            end_equity = points[-1].total_equity
            result.append(
                PeriodReturn(
                    period=key,
                    start_equity=start_equity,
                    end_equity=end_equity,
                    return_rate=self._safe_return(start_equity, end_equity),
                )
            )
            previous_end_equity = end_equity
        return result
