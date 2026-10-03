from abc import abstractmethod
from typing import Protocol, Any, Mapping

import polars as pl

from .context import Context


class Factor(Protocol):
    name: str
    version: str
    value_type: str
    output_column: str

    def __init__(self, params: Mapping[str, Any]) -> None:
        self.params = params

    @abstractmethod
    def inputs(self) -> list[str]: ...

    @abstractmethod
    def compute(self, context: Context) -> dict[str, pl.DataFrame]: ...
