from typing import Any

from modules.config import resolve_project_path, DEFAULT_INDICATOR_ROOT
from modules.controller.base import rest_controller, get_mapping
from modules.indicators.indicator_service import IndicatorService
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.indicators.storage import IndicatorStore


@rest_controller("/indicator")
class IndicatorController:
    def __init__(self):
        super().__init__()
        self.database = SQLiteDatabase()
        self.indicator_store = IndicatorStore(
            resolve_project_path(DEFAULT_INDICATOR_ROOT)
        )
        self.indicator_service = IndicatorService(self.database, self.indicator_store)

    @get_mapping("/list")
    def get_indicator_list(
        self, stock_id: int, start_date: str, end_date: str, names: str
    ) -> list[dict[str, Any]]:
        with RepositorySession(self.database) as session:
            stock_info = session.stock_info.get(stock_id)
            if stock_info is None:
                return []

        dataset = self.indicator_service.get_indicator_dataset(
            stock_info=stock_info,
            start_date=start_date,
            end_date=end_date,
            names=list(map(str.strip, names.split(","))),
        )
        return dataset.to_dicts()
