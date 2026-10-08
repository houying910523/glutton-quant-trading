import importlib
import json

from modules.core import Factor
from modules.repositories.models import FactorMetaRecord


def create_factor(factor: FactorMetaRecord) -> Factor:
    module_name, separator, class_name = factor.impl_ref.partition(":")
    if not separator or not module_name or not class_name:
        raise ValueError("impl_ref must use the format 'module.path:ClassName'")

    module = importlib.import_module(module_name)
    clazz = getattr(module, class_name)
    instance = clazz(json.loads(factor.params or "{}"))
    if not isinstance(instance, Factor):
        raise TypeError("loaded impl_ref object is not a Factor instance")
    return instance
