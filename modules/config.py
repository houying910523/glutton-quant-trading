from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DATA_PATH / "system/glutton.db"
DEFAULT_RAW_ROOT = DATA_PATH / "raw"
DEFAULT_INDICATOR_ROOT = DATA_PATH / "indicators"


def resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
