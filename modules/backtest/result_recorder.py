from __future__ import annotations

from modules.backtest.models import BacktestResult, FillRecord, OrderIntent, TradeRecord


class ResultRecorder:
    """集中负责向 BacktestResult 追加订单、成交和闭合交易记录。"""

    def __init__(self, result: BacktestResult) -> None:
        """绑定本次回测结果对象，后续记录都会写入该对象。"""
        self.result = result

    def append_trade_record(
        self,
        *,
        instrument_id: str,
        open_date: str,
        close_date: str,
        quantity: int,
        entry_price: float,
        exit_price: float,
        pnl: float,
        return_rate: float,
    ) -> str:
        """追加一条已闭合交易记录，并返回生成的交易编号。"""
        trade_id = (
            f"TRD-{close_date.replace('-', '')}-{len(self.result.trades) + 1:06d}"
        )
        self.result.trades.append(
            TradeRecord(
                trade_id=trade_id,
                instrument_id=instrument_id,
                open_date=open_date,
                close_date=close_date,
                quantity=quantity,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=pnl,
                return_rate=return_rate,
            )
        )
        return trade_id

    def append_order_record(
        self,
        *,
        trade_date: str,
        instrument_id: str,
        side: str,
        quantity: int,
        requested_price: float | None,
        status: str,
        reason: str,
        status_detail: str = "",
    ) -> str:
        """追加一条订单意图记录，并返回生成的订单编号。"""
        order_id = (
            f"ORD-{trade_date.replace('-', '')}-{len(self.result.orders) + 1:06d}"
        )
        self.result.orders.append(
            OrderIntent(
                order_id=order_id,
                trade_date=trade_date,
                instrument_id=instrument_id,
                side=side,
                quantity=quantity,
                requested_price=requested_price,
                status=status,
                reason=reason,
                status_detail=status_detail,
            )
        )
        return order_id

    def record_rejected_order(
        self,
        *,
        trade_date: str,
        instrument_id: str,
        side: str,
        quantity: int,
        requested_price: float | None,
        reason: str,
        status_detail: str,
        constraint_key: str | None = None,
    ) -> str:
        """记录拒单，并可同步累加对应的约束计数。"""
        if constraint_key is not None:
            self.increment_constraint_count(constraint_key)
        return self.append_order_record(
            trade_date=trade_date,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            requested_price=requested_price,
            status="rejected",
            reason=reason,
            status_detail=status_detail,
        )

    def append_fill_record(
        self,
        *,
        order_id: str,
        trade_date: str,
        instrument_id: str,
        side: str,
        quantity: int,
        price: float,
        commission: float,
        stamp_duty: float,
        transfer_fee: float,
        requested_price: float,
        amount: float,
    ) -> None:
        """追加一条实际成交记录。"""
        fill_id = f"FIL-{trade_date.replace('-', '')}-{len(self.result.fills) + 1:06d}"
        self.result.fills.append(
            FillRecord(
                fill_id=fill_id,
                order_id=order_id,
                trade_date=trade_date,
                instrument_id=instrument_id,
                side=side,
                quantity=quantity,
                price=price,
                commission=commission,
                stamp_duty=stamp_duty,
                transfer_fee=transfer_fee,
                slippage=abs(price - requested_price) * quantity,
                amount=amount,
            )
        )

    def increment_constraint_count(
        self,
        key: str,
    ) -> None:
        """累加 metadata.constraint_counts 中的指定约束计数。"""
        counts = self.result.metadata.setdefault("constraint_counts", {})
        counts[key] = int(counts.get(key, 0)) + 1
