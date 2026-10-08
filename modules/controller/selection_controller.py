from modules.controller.base import rest_controller, get_mapping, post_mapping
from modules.controller.object import SelectionRequest
from modules.filters import FilterMeta, create_filter
from modules.repositories import RepositorySession
from modules.repositories.database import SQLiteDatabase
from modules.repositories.models import StockInfoRecord
from modules.research.selection import Selection


@rest_controller("/selection")
class SelectionController:
    def __init__(self):
        self.database = SQLiteDatabase()

    @get_mapping("/filters")
    def list_filters(self) -> list[FilterMeta]:
        from modules.filters import list_filters

        return list_filters()

    @post_mapping("/select")
    def select(self, request: SelectionRequest) -> list[StockInfoRecord]:
        filters = [
            create_filter(filter_params.filter, filter_params.params)
            for filter_params in request.filters
        ]
        selection = Selection(self.database)
        data = selection.run(filters, request.optional)
        symbols = [record.instrument_id.split(".")[0] for record in data]
        with RepositorySession(self.database) as session:
            return session.stock_info.find_by_symbols(symbols)
