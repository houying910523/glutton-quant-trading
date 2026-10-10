from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StrategyMeta:
    id: int
    name: str
    description: str = ""
    frequency: str = "1d"
    lookback_days: int = 0
    inputs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TargetPosition:
    """决策式策略输出的目标仓位。"""

    instrument_id: str
    target_weight: float
    reason: str = ""


@dataclass(frozen=True)
class StrategyDecision:
    """决策式策略输出。"""

    as_of_date: str
    targets: list[TargetPosition] = field(default_factory=list)
    close_missing_positions: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
