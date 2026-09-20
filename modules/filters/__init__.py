from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.core import Filter


def _to_filter_class_name(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_")) + "Filter"


def create_filter(name: str) -> Filter:
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
    return clazz()
