from dataclasses import dataclass, field


@dataclass(frozen=True)
class StrategyMeta:
    id: int
    name: str
    description: str = ""
    frequency: str = "1d"
    lookback_days: int = 0
    inputs: list[str] = field(default_factory=list)


@dataclass
class Signal:
    """交易信号，策略输出，引擎负责下单"""

    symbol: str
    direction: str  # long / short / flat
    signal_type: str  # open / close
    price: float | None = None
    volume: int | None = None
    reason: str = ""
