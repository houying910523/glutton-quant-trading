from dataclasses import dataclass
from typing import Any

import pandas as pd

from modules.repositories.models import StockRecord


@dataclass(slots=True)
class StrategyInput:
    # 策略参数
    params: dict[str, Any]

    # 行情数据
    dataset: pd.DataFrame

    # 股票信息
    stock: StockRecord
