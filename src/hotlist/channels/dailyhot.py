"""Rate-limited client for the public DailyHot API fallback."""

import os
import time

from src.utils.http_utils import get


DEFAULT_MIN_INTERVAL_SECONDS = 5.0
DEFAULT_COOLDOWN_SECONDS = 600.0
_CACHE: dict[str, object] = {}
_last_request_at: float | None = None
_blocked_until = 0.0


def reset_request_state() -> None:
    global _last_request_at, _blocked_until
    _CACHE.clear()
    _last_request_at = None
    _blocked_until = 0.0


def _minimum_interval() -> float:
    raw = os.environ.get("HOTLIST_DAILYHOT_MIN_INTERVAL_SECONDS", "").strip()
    try:
        return max(0.0, float(raw)) if raw else DEFAULT_MIN_INTERVAL_SECONDS
    except ValueError:
        return DEFAULT_MIN_INTERVAL_SECONDS


def fetch_payload(url: str):
    global _last_request_at, _blocked_until
    if url in _CACHE:
        return _CACHE[url]
    requested_at = time.monotonic()
    if requested_at < _blocked_until:
        raise RuntimeError("DailyHot API 处于请求冷却期，本批次停止继续访问")
    if _last_request_at is not None:
        wait = _minimum_interval() - (requested_at - _last_request_at)
        if wait > 0:
            time.sleep(wait)
            requested_at = time.monotonic()
    _last_request_at = requested_at
    try:
        payload = get(url, res_type="json", timeout=20, retries=1)
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in {403, 429}:
            _blocked_until = requested_at + DEFAULT_COOLDOWN_SECONDS
            raise RuntimeError("DailyHot API 触发访问限制，本批次进入请求冷却") from exc
        raise
    _CACHE[url] = payload
    return payload
