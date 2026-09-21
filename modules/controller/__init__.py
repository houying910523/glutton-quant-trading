from importlib import import_module
from pkgutil import walk_packages


def load_controllers() -> None:
    """Import all controller modules so decorators can register controllers."""

    for module_info in walk_packages(__path__, prefix=f"{__name__}."):
        if module_info.name.endswith(".base"):
            continue
        import_module(module_info.name)
