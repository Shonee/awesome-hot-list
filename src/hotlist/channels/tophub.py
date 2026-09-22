"""Reusable TodayHot ranking-page provider for channel fallbacks."""

import os
import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import EmptySourceError, HotItem


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Referer": "https://tophub.today/",
}

DEFAULT_MIN_INTERVAL_SECONDS = 3.0
DEFAULT_COOLDOWN_SECONDS = 300.0
_PAGE_CACHE: dict[str, str] = {}
_last_request_at: float | None = None
_blocked_until = 0.0


def reset_request_state() -> None:
    """Reset process-local provider state for tests and explicit batch boundaries."""
    global _blocked_until, _last_request_at

    _PAGE_CACHE.clear()
    _last_request_at = None
    _blocked_until = 0.0


def _minimum_interval() -> float:
    raw = os.environ.get("HOTLIST_TOPHUB_MIN_INTERVAL_SECONDS", "").strip()
    try:
        return max(0.0, float(raw)) if raw else DEFAULT_MIN_INTERVAL_SECONDS
    except ValueError:
        return DEFAULT_MIN_INTERVAL_SECONDS


def _fetch_page(page_url: str) -> str:
    """Fetch one page with shared throttling and process-local deduplication."""
    global _blocked_until, _last_request_at

    if page_url in _PAGE_CACHE:
        return _PAGE_CACHE[page_url]

    requested_at = time.monotonic()
    if requested_at < _blocked_until:
        raise RuntimeError("今日热榜处于请求冷却期，本批次停止继续访问")
    if _last_request_at is not None:
        wait = _minimum_interval() - (requested_at - _last_request_at)
        if wait > 0:
            time.sleep(wait)
            requested_at = time.monotonic()
    _last_request_at = requested_at

    # A batch may use several TodayHot-backed channels. Avoid multiplying a
    # provider-side 429 into another burst of immediate retries.
    try:
        html = get(page_url, headers=HEADERS, retries=1)
    except Exception as exc:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        if status in {403, 429}:
            retry_after = getattr(response, "headers", {}).get("Retry-After", "")
            try:
                retry_after_seconds = max(0.0, float(retry_after))
            except (TypeError, ValueError):
                retry_after_seconds = 0.0
            _blocked_until = requested_at + max(
                DEFAULT_COOLDOWN_SECONDS,
                retry_after_seconds,
            )
            raise RuntimeError("今日热榜触发访问限制，本批次进入请求冷却") from exc
        raise
    _PAGE_CACHE[page_url] = html
    return html


def _host_allowed(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return any(
        hostname == allowed.lower() or hostname.endswith(f".{allowed.lower()}")
        for allowed in allowed_hosts
    )


def _rank(row, fallback: int) -> int:
    first_cell = row.find("td")
    text = first_cell.get_text(" ", strip=True) if first_cell else ""
    match = re.search(r"\d+", text)
    return int(match.group()) if match else fallback


def parse_ranking(
    html: str,
    allowed_hosts: tuple[str, ...],
    limit: int = 50,
) -> list[HotItem]:
    """Parse one public TodayHot table and reject unrelated target links."""
    soup = BeautifulSoup(html or "", "html.parser")
    table = soup.select_one("table.table")
    if not table:
        return []

    items = []
    seen = set()
    for fallback_rank, row in enumerate(table.select("tbody > tr"), 1):
        content_link = None
        for link in row.select("a[href]"):
            title = link.get_text(" ", strip=True)
            url = urljoin("https://tophub.today/", link.get("href", ""))
            if (
                not title
                or link.get("title") == "查看详细"
                or not _host_allowed(url, allowed_hosts)
            ):
                continue
            content_link = (title, url)
            break
        if not content_link:
            continue

        title, url = content_link
        dedupe_key = (title, url)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        hot_node = row.select_one(".item-desc, .ws")
        image = row.select_one("img[src]")
        items.append(
            HotItem(
                rank=_rank(row, fallback_rank),
                title=title,
                url=url,
                hot=hot_node.get_text(" ", strip=True) if hot_node else None,
                image_url=urljoin("https://tophub.today/", image.get("src", "")) if image else "",
            )
        )
        if len(items) >= max(1, min(50, int(limit))):
            break
    return items


def fetch_ranking(
    page_url: str,
    allowed_hosts: tuple[str, ...],
    limit: int = 50,
    min_items: int = 5,
) -> list[HotItem]:
    items = parse_ranking(_fetch_page(page_url), allowed_hosts, limit=limit)
    if len(items) < max(1, int(min_items)):
        raise EmptySourceError(f"今日热榜仅返回 {len(items)} 条有效数据")
    return items
