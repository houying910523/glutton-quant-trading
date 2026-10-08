from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from modules.filters.filter import Filter
from modules.filters.models import FilterMeta


def _to_filter_class_name(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_")) + "Filter"


def create_filter(name: str, params: dict[str, Any] | None = None) -> Filter:
    module_name = f"{__name__}.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise ValueError(f"unsupported filter: {name}") from exc
        raise

    class_name = _to_filter_class_name(name)
    clazz = getattr(module, class_name, None)
    if clazz is None:
        raise ValueError(f"filter module '{module_name}' must define '{class_name}'")
    return clazz(params)


def list_filters() -> list[FilterMeta]:
    filters: list[FilterMeta] = []
    for module_info in sorted(
        pkgutil.iter_modules(__path__), key=lambda item: item.name
    ):
        if module_info.name.startswith("_"):
            continue

        module = importlib.import_module(f"{__name__}.{module_info.name}")
        clazz = getattr(module, _to_filter_class_name(module_info.name), None)
        if clazz is None:
            continue

        name = getattr(clazz, "name", None)
        if not isinstance(name, str) or not name:
            continue

        filters.append(
            FilterMeta(
                label=name,
                name=module_info.name,
                description=inspect.cleandoc(clazz.__doc__ or ""),
                params_schema=getattr(clazz, "params_schema", []),
            )
        )

    return filters
