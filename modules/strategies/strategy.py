from abc import ABC, abstractmethod
from typing import Any


class Strategy(ABC):
    @abstractmethod
    def run(self, strategy_input: Any) -> None: ...
