from __future__ import annotations

from dataclasses import dataclass

from modules.backtest.result_recorder import ResultRecorder


def safe_return(start_value: float, end_value: float) -> float:
    """计算收益率；成本基数无效时返回 0。"""
    if start_value <= 0:
        return 0.0
    return (end_value / start_value) - 1.0


@dataclass
class OpenTradeLot:
    """尚未完全平仓的一批开仓记录。"""

    open_date: str
    quantity: int
    entry_price: float
    remaining_entry_cost: float = 0.0


class TradeLedger:
    """维护 FIFO 开仓批次，并在卖出时生成闭合交易记录。"""

    def __init__(
        self,
        *,
        recorder: ResultRecorder,
        open_trade_lots: dict[str, list[OpenTradeLot]] | None = None,
    ) -> None:
        """绑定结果记录器，并允许测试注入已有开仓批次。"""
        self.recorder = recorder
        self.open_trade_lots = open_trade_lots if open_trade_lots is not None else {}

    def record_open_trade_lot(
        self,
        *,
        instrument_id: str,
        open_date: str,
        quantity: int,
        entry_price: float,
        entry_cost: float,
    ) -> None:
        """记录一次买入形成的开仓批次。"""
        if quantity <= 0:
            return
        self.open_trade_lots.setdefault(instrument_id, []).append(
            OpenTradeLot(
                open_date=open_date,
                quantity=quantity,
                entry_price=entry_price,
                remaining_entry_cost=entry_cost,
            )
        )

    def record_closed_trades(
        self,
        *,
        instrument_id: str,
        close_date: str,
        exit_price: float,
        quantity: int,
        exit_cost: float,
    ) -> None:
        """按 FIFO 匹配卖出数量，并把已闭合部分写入交易记录。"""
        remaining_quantity = quantity
        lots = self.open_trade_lots.get(instrument_id, [])
        if remaining_quantity <= 0 or not lots:
            return

        total_exit_quantity = quantity
        while remaining_quantity > 0 and lots:
            lot = lots[0]
            matched_quantity = min(remaining_quantity, lot.quantity)
            if matched_quantity <= 0:
                break

            entry_cost = 0.0
            if lot.remaining_entry_cost > 0 and lot.quantity > 0:
                entry_cost = lot.remaining_entry_cost * matched_quantity / lot.quantity
            exit_cost_alloc = 0.0
            if exit_cost > 0 and total_exit_quantity > 0:
                exit_cost_alloc = exit_cost * matched_quantity / total_exit_quantity
            pnl = (
                (exit_price - lot.entry_price) * matched_quantity
                - entry_cost
                - exit_cost_alloc
            )
            cost_basis = lot.entry_price * matched_quantity + entry_cost
            return_rate = safe_return(cost_basis, cost_basis + pnl)
            self.recorder.append_trade_record(
                instrument_id=instrument_id,
                open_date=lot.open_date,
                close_date=close_date,
                quantity=matched_quantity,
                entry_price=lot.entry_price,
                exit_price=exit_price,
                pnl=pnl,
                return_rate=return_rate,
            )

            lot.quantity -= matched_quantity
            lot.remaining_entry_cost = max(
                0.0,
                lot.remaining_entry_cost - entry_cost,
            )
            remaining_quantity -= matched_quantity
            if lot.quantity <= 0:
                lots.pop(0)

        if not lots:
            self.open_trade_lots.pop(instrument_id, None)
