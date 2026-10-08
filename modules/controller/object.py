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
