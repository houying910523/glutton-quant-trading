from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from typing import Any

import polars as pl

from modules.indicators.models import IndicatorSpec, IndicatorDefinition


class Indicator(ABC):
    @abstractmethod
    def spec(self, params: dict[str, Any]) -> IndicatorSpec: ...

    @abstractmethod
    def compute(
        self,
        frame: pl.DataFrame,
        params: dict[str, Any],
    ) -> pl.DataFrame: ...


def load_factor(definition: IndicatorDefinition) -> Indicator:
    module_name, separator, class_name = definition.compute_ref.partition(":")
    if not separator or not module_name or not class_name:
        raise ValueError("compute_ref must use the format 'module.path:ClassName'")

    module = importlib.import_module(module_name)
    clazz = getattr(module, class_name)
    instance = clazz()
    if not isinstance(instance, Indicator):
        raise TypeError("loaded compute_ref object is not a Factor instance")
    return instance
