from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data/system/glutton.db"
DEFAULT_RAW_ROOT = PROJECT_ROOT / "data/raw"
