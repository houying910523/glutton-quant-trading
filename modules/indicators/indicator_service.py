from modules.indicators.storage import IndicatorStore


class IndicatorService:
    def __init__(self, store: IndicatorStore):
        self.store = store
