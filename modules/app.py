from fastapi import FastAPI

from modules.datasource.service.stock_daily_service import StockDailyService
from modules.indicators.indicator_service import IndicatorService
from modules.indicators.storage import IndicatorStore
from modules.repositories.database import SQLiteDatabase
from modules.repositories.schema import SQLiteSchemaManager


class App:
    def __init__(self) -> None:
        self.api = FastAPI(
            title="Glutton Quant Trading API",
            version="1.0.0",
            description="Glutton Quant Trading API",
        )
        self._database = SQLiteDatabase()
        self._schema_manager = SQLiteSchemaManager(self._database)
        self._schema_manager.initialize()

        # 股票日数据
        self._stock_daily_service = StockDailyService(self._database)

        # 指标
        from modules.config import PROJECT_ROOT

        self._indicator_store = IndicatorStore(
            indicator_root=PROJECT_ROOT / "indicators"
        )
        self._indicator_service = IndicatorService(self._indicator_store)
        self.mount_api()

    @property
    def database(self) -> SQLiteDatabase:
        return self._database

    def mount_api(self) -> None:
        from modules.controller import load_controllers
        from modules.controller.base import routers

        load_controllers()
        for path, router in routers:
            self.api.include_router(router, prefix=path)


runtime = App()
app = runtime.api
