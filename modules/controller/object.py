from typing import Any

from pydantic import BaseModel


class StockOptionalRequest(BaseModel):
    action: str = "add"
    stock_id: int


class StockDailyRow(BaseModel):
    stock_id: int
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: int
    turnover: float


class FilterParams(BaseModel):
    filter: str
    params: dict[str, int | float]


class SelectionRequest(BaseModel):
    filters: list[FilterParams] = []
    optional: bool = False


class BacktestConfigRequest(BaseModel):
    start_date: str
    end_date: str
    initial_cash: float = 1_000_000.0
    rebalance_frequency: str = "monthly"
    commission_rate: float = 0.0003
    minimum_commission: float = 0.0
    stamp_duty_rate: float = 0.0
    transfer_fee_rate: float = 0.0
    slippage_rate: float = 0.0005
    optional: bool = False
    instruments: list[str] = []
    data_columns: list[str] = []
    metadata: dict[str, Any] = {}


class BacktestRunRequest(BaseModel):
    strategy_id: str
    strategy_params: dict[str, Any] = {}
    config: BacktestConfigRequest
