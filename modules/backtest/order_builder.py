from __future__ import annotations

import math

from modules.backtest.market_data import DailyBarLookup
from modules.backtest.models import PortfolioPosition, PortfolioState
from modules.backtest.orders import ScheduledOrder
from modules.backtest.result_recorder import ResultRecorder
from modules.backtest.rules import DEFAULT_MARKET_RULES, MarketRules
from modules.strategies.models import StrategyDecision, TargetPosition


class RebalanceOrderBuilder:
    """把策略目标仓位转换为下一交易日待执行订单。"""

    def __init__(
        self,
        *,
        bar_lookup: DailyBarLookup,
        recorder: ResultRecorder,
        rules: MarketRules = DEFAULT_MARKET_RULES,
    ) -> None:
        """绑定行情查询、结果记录器和市场规则。"""
        self.bar_lookup = bar_lookup
        self.recorder = recorder
        self.rules = rules

    def build(
        self,
        *,
        decision: StrategyDecision,
        pricing_date: str,
        execution_date: str,
        portfolio_state: PortfolioState,
    ) -> list[ScheduledOrder]:
        """生成调仓订单，并记录无法换算成有效买入股数的拒单。"""
        target_map = self.normalize_targets(decision.targets)
        desired_quantities, missing_price_instruments, below_board_lot_targets = (
            self.build_target_quantities(
                target_map=target_map,
                pricing_date=pricing_date,
                total_equity=portfolio_state.total_equity,
            )
        )

        orders: list[ScheduledOrder] = []
        current_symbols = set(portfolio_state.positions.keys())
        target_symbols = set(target_map.keys())

        for instrument_id in sorted(current_symbols):
            current_quantity = portfolio_state.positions[instrument_id].quantity
            if instrument_id in desired_quantities:
                desired_quantity = desired_quantities[instrument_id]
            elif instrument_id in below_board_lot_targets:
                desired_quantity = 0
            elif instrument_id in target_map:
                desired_quantity = current_quantity
            else:
                desired_quantity = (
                    0 if decision.close_missing_positions else current_quantity
                )
            sell_quantity = max(0, current_quantity - desired_quantity)
            if sell_quantity <= 0:
                continue
            target = target_map.get(instrument_id)
            order_reason = (
                target.reason
                if target is not None
                else "rebalance_close_missing_position"
            )
            orders.append(
                ScheduledOrder(
                    trade_date=execution_date,
                    instrument_id=instrument_id,
                    side="sell",
                    quantity=sell_quantity,
                    reason=order_reason,
                )
            )

        for instrument_id in sorted(target_symbols):
            current_quantity = portfolio_state.positions.get(
                instrument_id,
                PortfolioPosition(instrument_id=instrument_id),
            ).quantity
            desired_quantity = desired_quantities.get(instrument_id)
            target = target_map.get(instrument_id)
            order_reason = target.reason if target is not None else "rebalance_target"
            if desired_quantity is None:
                if instrument_id in missing_price_instruments:
                    self.recorder.record_rejected_order(
                        trade_date=execution_date,
                        instrument_id=instrument_id,
                        side="buy",
                        quantity=0,
                        requested_price=None,
                        reason=order_reason,
                        status_detail="no_close_price",
                        constraint_key="skipped_no_price_orders",
                    )
                elif instrument_id in below_board_lot_targets:
                    raw_quantity, order_price = below_board_lot_targets[instrument_id]
                    net_buy_quantity = max(0, raw_quantity - current_quantity)
                    if net_buy_quantity > 0:
                        self.recorder.record_rejected_order(
                            trade_date=execution_date,
                            instrument_id=instrument_id,
                            side="buy",
                            quantity=net_buy_quantity,
                            requested_price=order_price,
                            reason=order_reason,
                            status_detail="below_board_lot",
                            constraint_key="below_board_lot_orders",
                        )
                continue
            buy_quantity = max(0, desired_quantity - current_quantity)
            if buy_quantity <= 0:
                continue
            orders.append(
                ScheduledOrder(
                    trade_date=execution_date,
                    instrument_id=instrument_id,
                    side="buy",
                    quantity=buy_quantity,
                    reason=order_reason,
                )
            )

        return orders

    def normalize_targets(
        self,
        targets: list[TargetPosition],
    ) -> dict[str, TargetPosition]:
        """校验并按标的归一化目标仓位，保证权重表达可执行。"""
        normalized: dict[str, TargetPosition] = {}
        total_weight = 0.0
        for target in targets:
            instrument_id = str(target.instrument_id).strip()
            if not instrument_id:
                raise ValueError("target instrument_id must not be empty")
            if instrument_id in normalized:
                raise ValueError(f"duplicate target instrument_id: {instrument_id}")
            target_weight = float(target.target_weight)
            if not math.isfinite(target_weight):
                raise ValueError(f"target_weight must be finite for {instrument_id}")
            if target_weight < 0:
                raise ValueError(
                    f"target_weight must be non-negative for {instrument_id}"
                )
            total_weight += target_weight
            normalized[instrument_id] = target
        if self.rules.target_weight_exceeds_limit(total_weight):
            raise ValueError("total target_weight must be less than or equal to 1")
        return normalized

    def build_target_quantities(
        self,
        *,
        target_map: dict[str, TargetPosition],
        pricing_date: str,
        total_equity: float,
    ) -> tuple[dict[str, int], set[str], dict[str, tuple[int, float]]]:
        """用定价日收盘价把目标权重换算为整手目标股数。"""
        desired_quantities: dict[str, int] = {}
        missing_price_instruments: set[str] = set()
        below_board_lot_targets: dict[str, tuple[int, float]] = {}
        for instrument_id, target in target_map.items():
            target_weight = float(target.target_weight)
            if target_weight <= 0:
                desired_quantities[instrument_id] = 0
                continue
            close_price = self.bar_lookup.price(pricing_date, instrument_id, "close")
            if close_price is None or close_price <= 0:
                missing_price_instruments.add(instrument_id)
                continue
            target_value = max(0.0, total_equity * target_weight)
            raw_quantity = int(target_value / close_price)
            quantity = self.rules.round_down_to_board_lot(raw_quantity)
            if quantity <= 0:
                if raw_quantity > 0:
                    below_board_lot_targets[instrument_id] = (
                        raw_quantity,
                        close_price,
                    )
                continue
            desired_quantities[instrument_id] = quantity
        return desired_quantities, missing_price_instruments, below_board_lot_targets
