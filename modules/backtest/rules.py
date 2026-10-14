from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRules:
    """回测执行使用的市场规则集合。"""

    board_lot_size: int = 100
    limit_move_threshold: float = 0.098
    same_price_tolerance: float = 1e-9

    def round_down_to_board_lot(self, quantity: int) -> int:
        """按整手规则向下取整到可买入股数。"""
        if quantity <= 0:
            return 0
        return int(quantity // self.board_lot_size * self.board_lot_size)

    def target_weight_exceeds_limit(self, total_weight: float) -> bool:
        """判断目标权重总和是否超过满仓上限。"""
        return total_weight > 1.0 + self.same_price_tolerance


DEFAULT_MARKET_RULES = MarketRules()

BOARD_LOT_SIZE = DEFAULT_MARKET_RULES.board_lot_size
LIMIT_MOVE_THRESHOLD = DEFAULT_MARKET_RULES.limit_move_threshold
SAME_PRICE_TOLERANCE = DEFAULT_MARKET_RULES.same_price_tolerance


def round_down_to_board_lot(quantity: int) -> int:
    """使用默认市场规则按整手向下取整。"""
    return DEFAULT_MARKET_RULES.round_down_to_board_lot(quantity)
