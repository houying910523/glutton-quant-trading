from __future__ import annotations

from modules.backtest.models import PortfolioState
from modules.core.context import Context
from modules.strategies.base import BaseStrategy
from modules.strategies.models import StrategyDecision, StrategyMeta, TargetPosition


class BuyAndHoldStrategy(BaseStrategy):
    """简单等权买入并持有策略，用于跑通回测主流程。"""

    def __init__(
        self,
        instrument_ids: list[str] | None = None,
        *,
        meta: StrategyMeta | None = None,
        total_weight: float = 1.0,
    ) -> None:
        """绑定目标股票池；未传入时从回测上下文中读取股票池。"""
        self.meta = meta or StrategyMeta(
            id=0,
            name="buy_and_hold",
            description="Equal weight buy-and-hold strategy.",
            lookback_days=1,
        )
        self.instrument_ids = list(instrument_ids or [])
        self.total_weight = float(total_weight)

    def decide(
        self,
        context: Context,
        portfolio_state: PortfolioState,
    ) -> StrategyDecision:
        """输出等权目标仓位；调仓差分由回测引擎负责。"""
        _ = portfolio_state
        instrument_ids = self.instrument_ids or self._context_instruments(context)
        if not instrument_ids:
            return StrategyDecision(
                as_of_date=context.end_date,
                targets=[],
                close_missing_positions=True,
                metadata={"selected_count": 0},
            )

        target_weight = self.total_weight / len(instrument_ids)
        targets = [
            TargetPosition(
                instrument_id=instrument_id,
                target_weight=target_weight,
                reason=f"buy_and_hold target_weight={target_weight:.6f}",
            )
            for instrument_id in sorted(instrument_ids)
        ]
        return StrategyDecision(
            as_of_date=context.end_date,
            targets=targets,
            close_missing_positions=True,
            metadata={"selected_count": len(targets)},
        )

    def _context_instruments(self, context: Context) -> list[str]:
        """从 Context 中提取可交易股票池。"""
        if context.stocks:
            return sorted(context.stocks.keys())
        return sorted(
            {
                stock_daily_data.instrument_id
                for stock_daily_data in context.stock_daily_data
            }
        )
