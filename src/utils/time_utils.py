"""Project-wide Asia/Shanghai time helpers."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


PROJECT_TIMEZONE = ZoneInfo("Asia/Shanghai")


def project_now() -> datetime:
    return datetime.now(PROJECT_TIMEZONE)


def now_string() -> str:
    return project_now().strftime("%Y-%m-%d %H:%M:%S")


def timestamp_string(value, fallback: str = "") -> str:
    try:
        return datetime.fromtimestamp(int(value), PROJECT_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OverflowError, OSError):
        return fallback


def date_string(days: int = 0, pattern: str = "%Y-%m-%d") -> str:
    return (project_now() + timedelta(days=days)).strftime(pattern)
