from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_shanghai() -> datetime:
    return datetime.now(tz=SHANGHAI_TZ)


def format_timestamp(value: datetime | None = None) -> str:
    current = value or now_shanghai()
    return current.astimezone(SHANGHAI_TZ).strftime(TIMESTAMP_FORMAT)


def parse_date(value: str | None) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    normalized = value.strip()
    if len(normalized) == 8 and normalized.isdigit():
        return datetime.strptime(normalized, "%Y%m%d").date()
    return datetime.strptime(normalized, "%Y-%m-%d").date()


def format_date(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = parse_date(value)
        return parsed.isoformat() if parsed else None
    return value.isoformat()


def compact_date(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = parse_date(value)
        return parsed.strftime("%Y%m%d") if parsed else None
    return value.strftime("%Y%m%d")
