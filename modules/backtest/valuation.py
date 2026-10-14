from __future__ import annotations

from modules.backtest.market_data import DailyBarLookup
from modules.backtest.models import PortfolioPosition, PortfolioState, PositionSnapshot


class PortfolioValuator:
    """使用收盘价维护组合市值、净值和持仓快照。"""

    def __init__(self, bar_lookup: DailyBarLookup) -> None:
        """绑定行情查询对象。"""
        self.bar_lookup = bar_lookup

    def mark_to_market(
        self,
        *,
        trade_date: str,
        portfolio_state: PortfolioState,
    ) -> int:
        """按交易日收盘价估值；缺失收盘价时沿用上一价格并计数。"""
        portfolio_state.as_of_date = trade_date
        stale_price_count = 0
        for instrument_id in list(portfolio_state.positions.keys()):
            position = portfolio_state.positions[instrument_id]
            if position.quantity <= 0:
                portfolio_state.positions.pop(instrument_id, None)
                continue
            close_price = self.bar_lookup.price(trade_date, instrument_id, "close")
            if close_price is not None and close_price > 0:
                position.last_price = close_price
            else:
                stale_price_count += 1
            position.available_quantity = min(
                position.available_quantity, position.quantity
            )
            last_price = position.last_price or 0.0
            position.market_value = float(last_price * position.quantity)
        return stale_price_count

    def build_position_snapshots(
        self,
        *,
        trade_date: str,
        portfolio_state: PortfolioState,
    ) -> list[PositionSnapshot]:
        """把当前组合持仓转换成当日持仓快照列表。"""
        total_equity = portfolio_state.total_equity
        snapshots: list[PositionSnapshot] = []
        for instrument_id in sorted(portfolio_state.positions.keys()):
            position = portfolio_state.positions[instrument_id]
            if position.quantity <= 0:
                continue
            weight = position.market_value / total_equity if total_equity > 0 else 0.0
            snapshots.append(
                PositionSnapshot(
                    trade_date=trade_date,
                    instrument_id=instrument_id,
                    quantity=position.quantity,
                    available_quantity=position.available_quantity,
                    average_cost=position.average_cost,
                    close_price=position.last_price,
                    market_value=position.market_value,
                    weight=weight,
                )
            )
        return snapshots

    def copy_portfolio_state(self, portfolio_state: PortfolioState) -> PortfolioState:
        """复制组合状态，避免最终结果继续引用运行时可变对象。"""
        copied_positions = {
            instrument_id: PortfolioPosition(
                instrument_id=position.instrument_id,
                quantity=position.quantity,
                available_quantity=position.available_quantity,
                average_cost=position.average_cost,
                last_price=position.last_price,
                market_value=position.market_value,
            )
            for instrument_id, position in portfolio_state.positions.items()
        }
        return PortfolioState(
            as_of_date=portfolio_state.as_of_date,
            cash=portfolio_state.cash,
            frozen_cash=portfolio_state.frozen_cash,
            positions=copied_positions,
        )

    def roll_position_availability(self, portfolio_state: PortfolioState) -> None:
        """进入新交易日时，把持仓数量滚动为可卖数量。"""
        for position in portfolio_state.positions.values():
            position.available_quantity = position.quantity
