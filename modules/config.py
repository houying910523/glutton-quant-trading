from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data/system/glutton.db"
DEFAULT_RAW_ROOT = PROJECT_ROOT / "data/raw"
DEFAULT_RESEARCH_ROOT = PROJECT_ROOT / "data/research"
DEFAULT_FACTOR_ROOT = DEFAULT_RESEARCH_ROOT / "factors"


def resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
