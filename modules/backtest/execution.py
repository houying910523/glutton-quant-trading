from __future__ import annotations

from dataclasses import dataclass

from modules.backtest.market_data import DailyBarLookup
from modules.backtest.models import BacktestConfig, PortfolioPosition, PortfolioState
from modules.backtest.orders import ScheduledOrder
from modules.backtest.result_recorder import ResultRecorder
from modules.backtest.rules import DEFAULT_MARKET_RULES, MarketRules
from modules.backtest.trade_ledger import TradeLedger


@dataclass
class BuyExecutionPlan:
    """买单批量分配现金时使用的临时执行计划。"""

    order: ScheduledOrder
    requested_quantity: int
    desired_quantity: int
    order_price: float
    fill_price: float
    required_cash: float
    allocated_quantity: int = 0


@dataclass(frozen=True)
class TradeCosts:
    """单笔成交拆分后的交易费用。"""

    commission: float = 0.0
    stamp_duty: float = 0.0
    transfer_fee: float = 0.0

    @property
    def total(self) -> float:
        """返回佣金、印花税和过户费之和。"""
        return self.commission + self.stamp_duty + self.transfer_fee


class OrderExecutor:
    """按 next_open 模型执行排定订单，并维护组合现金和持仓。"""

    def __init__(
        self,
        *,
        bar_lookup: DailyBarLookup,
        recorder: ResultRecorder,
        ledger: TradeLedger,
        config: BacktestConfig,
        rules: MarketRules = DEFAULT_MARKET_RULES,
    ) -> None:
        """绑定执行所需的行情、记录器、交易台账、配置和市场规则。"""
        self.bar_lookup = bar_lookup
        self.recorder = recorder
        self.ledger = ledger
        self.config = config
        self.rules = rules

    def execute_scheduled_orders(
        self,
        *,
        scheduled_orders: list[ScheduledOrder],
        trade_date: str,
        portfolio_state: PortfolioState,
    ) -> float:
        """按订单顺序执行；连续买单会合并成一个现金分配批次。"""
        turnover_amount = 0.0
        order_index = 0
        while order_index < len(scheduled_orders):
            scheduled_order = scheduled_orders[order_index]
            if scheduled_order.side != "buy":
                turnover_amount += self.execute_non_buy_order(
                    scheduled_order=scheduled_order,
                    trade_date=trade_date,
                    portfolio_state=portfolio_state,
                )
                order_index += 1
                continue

            buy_block: list[ScheduledOrder] = []
            while (
                order_index < len(scheduled_orders)
                and scheduled_orders[order_index].side == "buy"
            ):
                buy_block.append(scheduled_orders[order_index])
                order_index += 1
            turnover_amount += self.execute_buy_block(
                scheduled_orders=buy_block,
                trade_date=trade_date,
                portfolio_state=portfolio_state,
            )

        portfolio_state.as_of_date = trade_date
        return turnover_amount

    def execute_non_buy_order(
        self,
        *,
        scheduled_order: ScheduledOrder,
        trade_date: str,
        portfolio_state: PortfolioState,
    ) -> float:
        """执行非买入订单；当前只处理卖出并应用 T+1 和跌停约束。"""
        instrument_id = scheduled_order.instrument_id
        side = scheduled_order.side
        requested_quantity = int(scheduled_order.quantity)
        if requested_quantity <= 0:
            return 0.0

        order_price = self.bar_lookup.price(trade_date, instrument_id, "open")
        if order_price is None or order_price <= 0:
            self.recorder.record_rejected_order(
                trade_date=trade_date,
                instrument_id=instrument_id,
                side=side,
                quantity=requested_quantity,
                requested_price=order_price,
                reason=scheduled_order.reason,
                status_detail="no_open_price",
                constraint_key="skipped_no_price_orders",
            )
            return 0.0

        if self.bar_lookup.is_limit_blocked(
            trade_date=trade_date,
            instrument_id=instrument_id,
            side=side,
        ):
            self.recorder.record_rejected_order(
                trade_date=trade_date,
                instrument_id=instrument_id,
                side=side,
                quantity=requested_quantity,
                requested_price=order_price,
                reason=scheduled_order.reason,
                status_detail="limit_blocked",
                constraint_key="limit_blocked_orders",
            )
            return 0.0

        if side != "sell":
            return 0.0

        current_position = portfolio_state.positions.get(instrument_id)
        if current_position is None or current_position.quantity <= 0:
            return 0.0
        filled_quantity = min(requested_quantity, current_position.available_quantity)
        if filled_quantity <= 0:
            self.recorder.record_rejected_order(
                trade_date=trade_date,
                instrument_id=instrument_id,
                side=side,
                quantity=requested_quantity,
                requested_price=order_price,
                reason=scheduled_order.reason,
                status_detail="t_plus_one_blocked",
                constraint_key="t_plus_one_blocked_orders",
            )
            return 0.0

        fill_price = order_price * (1.0 - self.config.slippage_rate)
        gross_amount = fill_price * filled_quantity
        costs = self.calculate_trade_costs(gross_amount=gross_amount, side="sell")
        portfolio_state.cash += gross_amount - costs.total
        remaining_quantity = current_position.quantity - filled_quantity
        remaining_available_quantity = max(
            0,
            current_position.available_quantity - filled_quantity,
        )
        if remaining_quantity <= 0:
            portfolio_state.positions.pop(instrument_id, None)
        else:
            current_position.quantity = remaining_quantity
            current_position.available_quantity = remaining_available_quantity
            current_position.last_price = fill_price
            current_position.market_value = float(fill_price * remaining_quantity)
        self.ledger.record_closed_trades(
            instrument_id=instrument_id,
            close_date=trade_date,
            exit_price=fill_price,
            quantity=filled_quantity,
            exit_cost=costs.total,
        )

        order_status = (
            "filled" if filled_quantity == requested_quantity else "partially_filled"
        )
        order_status_detail = (
            "" if filled_quantity == requested_quantity else "t_plus_one_blocked"
        )
        order_id = self.recorder.append_order_record(
            trade_date=trade_date,
            instrument_id=instrument_id,
            side=side,
            quantity=requested_quantity,
            requested_price=order_price,
            status=order_status,
            reason=scheduled_order.reason,
            status_detail=order_status_detail,
        )
        self.recorder.append_fill_record(
            order_id=order_id,
            trade_date=trade_date,
            instrument_id=instrument_id,
            side=side,
            quantity=filled_quantity,
            price=fill_price,
            commission=costs.commission,
            stamp_duty=costs.stamp_duty,
            transfer_fee=costs.transfer_fee,
            requested_price=order_price,
            amount=gross_amount,
        )
        return gross_amount

    def execute_buy_block(
        self,
        *,
        scheduled_orders: list[ScheduledOrder],
        trade_date: str,
        portfolio_state: PortfolioState,
    ) -> float:
        """执行一组连续买单，并在现金不足时按整手分配可成交数量。"""
        execution_plans: list[BuyExecutionPlan] = []
        for scheduled_order in scheduled_orders:
            requested_quantity = int(scheduled_order.quantity)
            if requested_quantity <= 0:
                continue

            order_price = self.bar_lookup.price(
                trade_date,
                scheduled_order.instrument_id,
                "open",
            )
            if order_price is None or order_price <= 0:
                self.recorder.record_rejected_order(
                    trade_date=trade_date,
                    instrument_id=scheduled_order.instrument_id,
                    side="buy",
                    quantity=requested_quantity,
                    requested_price=order_price,
                    reason=scheduled_order.reason,
                    status_detail="no_open_price",
                    constraint_key="skipped_no_price_orders",
                )
                continue

            if self.bar_lookup.is_limit_blocked(
                trade_date=trade_date,
                instrument_id=scheduled_order.instrument_id,
                side="buy",
            ):
                self.recorder.record_rejected_order(
                    trade_date=trade_date,
                    instrument_id=scheduled_order.instrument_id,
                    side="buy",
                    quantity=requested_quantity,
                    requested_price=order_price,
                    reason=scheduled_order.reason,
                    status_detail="limit_blocked",
                    constraint_key="limit_blocked_orders",
                )
                continue

            desired_quantity = self.rules.round_down_to_board_lot(requested_quantity)
            if desired_quantity <= 0:
                self.recorder.record_rejected_order(
                    trade_date=trade_date,
                    instrument_id=scheduled_order.instrument_id,
                    side="buy",
                    quantity=requested_quantity,
                    requested_price=order_price,
                    reason=scheduled_order.reason,
                    status_detail="below_board_lot",
                    constraint_key="below_board_lot_orders",
                )
                continue

            fill_price = order_price * (1.0 + self.config.slippage_rate)
            required_cash = self.buy_cash_cost(
                fill_price=fill_price,
                quantity=desired_quantity,
            )
            if required_cash <= 0:
                continue
            execution_plans.append(
                BuyExecutionPlan(
                    order=scheduled_order,
                    requested_quantity=requested_quantity,
                    desired_quantity=desired_quantity,
                    order_price=order_price,
                    fill_price=fill_price,
                    required_cash=required_cash,
                )
            )

        if not execution_plans:
            return 0.0

        self.allocate_buy_quantities(
            execution_plans=execution_plans,
            available_cash=portfolio_state.cash,
        )

        turnover_amount = 0.0
        for plan in execution_plans:
            filled_quantity = plan.allocated_quantity
            if filled_quantity > 0:
                max_affordable_quantity = self.max_affordable_buy_quantity(
                    fill_price=plan.fill_price,
                    desired_quantity=filled_quantity,
                    available_cash=portfolio_state.cash,
                )
                filled_quantity = min(filled_quantity, max_affordable_quantity)

            if filled_quantity <= 0:
                self.recorder.record_rejected_order(
                    trade_date=trade_date,
                    instrument_id=plan.order.instrument_id,
                    side="buy",
                    quantity=plan.desired_quantity,
                    requested_price=plan.order_price,
                    reason=plan.order.reason,
                    status_detail="insufficient_cash",
                    constraint_key="insufficient_cash_orders",
                )
                continue

            order_status = "filled"
            order_status_detail = ""
            if filled_quantity < plan.desired_quantity:
                self.recorder.increment_constraint_count("insufficient_cash_orders")
                order_status = "partially_filled"
                order_status_detail = "insufficient_cash"

            gross_amount = plan.fill_price * filled_quantity
            costs = self.calculate_trade_costs(gross_amount=gross_amount, side="buy")
            total_cash_cost = gross_amount + costs.total
            portfolio_state.cash -= total_cash_cost
            current_position = portfolio_state.positions.get(plan.order.instrument_id)
            if current_position is None:
                portfolio_state.positions[plan.order.instrument_id] = PortfolioPosition(
                    instrument_id=plan.order.instrument_id,
                    quantity=filled_quantity,
                    available_quantity=0,
                    average_cost=plan.fill_price,
                    last_price=plan.fill_price,
                    market_value=0.0,
                )
            else:
                total_quantity = current_position.quantity + filled_quantity
                if total_quantity <= 0:
                    continue
                current_position.average_cost = (
                    current_position.average_cost * current_position.quantity
                    + plan.fill_price * filled_quantity
                ) / total_quantity
                current_position.quantity = total_quantity
                current_position.last_price = plan.fill_price

            self.ledger.record_open_trade_lot(
                instrument_id=plan.order.instrument_id,
                open_date=trade_date,
                quantity=filled_quantity,
                entry_price=plan.fill_price,
                entry_cost=costs.total,
            )
            order_id = self.recorder.append_order_record(
                trade_date=trade_date,
                instrument_id=plan.order.instrument_id,
                side="buy",
                quantity=plan.desired_quantity,
                requested_price=plan.order_price,
                status=order_status,
                reason=plan.order.reason,
                status_detail=order_status_detail,
            )
            self.recorder.append_fill_record(
                order_id=order_id,
                trade_date=trade_date,
                instrument_id=plan.order.instrument_id,
                side="buy",
                quantity=filled_quantity,
                price=plan.fill_price,
                commission=costs.commission,
                stamp_duty=costs.stamp_duty,
                transfer_fee=costs.transfer_fee,
                requested_price=plan.order_price,
                amount=gross_amount,
            )
            turnover_amount += gross_amount

        return turnover_amount

    def allocate_buy_quantities(
        self,
        *,
        execution_plans: list[BuyExecutionPlan],
        available_cash: float,
    ) -> None:
        """在多个买单之间分配可用现金，分配结果写回执行计划。"""
        if available_cash <= 0 or not execution_plans:
            return

        total_required_cash = sum(plan.required_cash for plan in execution_plans)
        if total_required_cash <= available_cash + self.rules.same_price_tolerance:
            for plan in execution_plans:
                plan.allocated_quantity = plan.desired_quantity
            return

        for plan in execution_plans:
            desired_lots = plan.desired_quantity // self.rules.board_lot_size
            ideal_lots = desired_lots * available_cash / total_required_cash
            plan.allocated_quantity = int(ideal_lots) * self.rules.board_lot_size

        remaining_cash = available_cash - sum(
            self.buy_cash_cost(
                fill_price=plan.fill_price,
                quantity=plan.allocated_quantity,
            )
            for plan in execution_plans
        )
        while remaining_cash > self.rules.same_price_tolerance:
            selected_plan: BuyExecutionPlan | None = None
            selected_priority: tuple[float, float, float] | None = None
            for plan in execution_plans:
                if plan.allocated_quantity >= plan.desired_quantity:
                    continue
                lot_cash_cost = self.incremental_buy_cash_cost(
                    fill_price=plan.fill_price,
                    current_quantity=plan.allocated_quantity,
                    add_quantity=self.rules.board_lot_size,
                )
                if lot_cash_cost > remaining_cash + self.rules.same_price_tolerance:
                    continue
                desired_lots = plan.desired_quantity // self.rules.board_lot_size
                allocated_lots = plan.allocated_quantity // self.rules.board_lot_size
                ideal_lots = desired_lots * available_cash / total_required_cash
                priority = (
                    ideal_lots - allocated_lots,
                    plan.required_cash,
                    -lot_cash_cost,
                )
                if (
                    selected_priority is None
                    or priority > selected_priority
                    or (
                        priority == selected_priority
                        and selected_plan is not None
                        and plan.order.instrument_id < selected_plan.order.instrument_id
                    )
                ):
                    selected_plan = plan
                    selected_priority = priority

            if selected_plan is None:
                break
            selected_plan.allocated_quantity += self.rules.board_lot_size
            remaining_cash -= self.incremental_buy_cash_cost(
                fill_price=selected_plan.fill_price,
                current_quantity=selected_plan.allocated_quantity
                - self.rules.board_lot_size,
                add_quantity=self.rules.board_lot_size,
            )

    def buy_cash_cost(
        self,
        *,
        fill_price: float,
        quantity: int,
    ) -> float:
        """计算买入指定股数需要冻结的现金总额。"""
        if quantity <= 0:
            return 0.0
        gross_amount = fill_price * quantity
        return (
            gross_amount
            + self.calculate_trade_costs(
                gross_amount=gross_amount,
                side="buy",
            ).total
        )

    def incremental_buy_cash_cost(
        self,
        *,
        fill_price: float,
        current_quantity: int,
        add_quantity: int,
    ) -> float:
        """计算在已有买入数量上追加一手或多手所需的边际现金。"""
        return self.buy_cash_cost(
            fill_price=fill_price,
            quantity=current_quantity + add_quantity,
        ) - self.buy_cash_cost(
            fill_price=fill_price,
            quantity=current_quantity,
        )

    def max_affordable_buy_quantity(
        self,
        *,
        fill_price: float,
        desired_quantity: int,
        available_cash: float,
    ) -> int:
        """在可用现金约束下求最大可买整手数量。"""
        desired_lots = desired_quantity // self.rules.board_lot_size
        low = 0
        high = desired_lots
        while low < high:
            mid = (low + high + 1) // 2
            quantity = mid * self.rules.board_lot_size
            if (
                self.buy_cash_cost(
                    fill_price=fill_price,
                    quantity=quantity,
                )
                <= available_cash + self.rules.same_price_tolerance
            ):
                low = mid
            else:
                high = mid - 1
        return low * self.rules.board_lot_size

    def calculate_trade_costs(
        self,
        *,
        gross_amount: float,
        side: str,
    ) -> TradeCosts:
        """按回测配置计算佣金、印花税和过户费。"""
        if gross_amount <= 0:
            return TradeCosts()
        commission = gross_amount * self.config.commission_rate
        if self.config.minimum_commission > 0 and commission > 0:
            commission = max(commission, self.config.minimum_commission)
        stamp_duty = (
            gross_amount * self.config.stamp_duty_rate if side == "sell" else 0.0
        )
        transfer_fee = gross_amount * self.config.transfer_fee_rate
        return TradeCosts(
            commission=float(commission),
            stamp_duty=float(stamp_duty),
            transfer_fee=float(transfer_fee),
        )
