"""Reusable TodayHot ranking-page provider for channel fallbacks."""

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Referer": "https://tophub.today/",
}


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
    items = parse_ranking(get(page_url, headers=HEADERS), allowed_hosts, limit=limit)
    if len(items) < max(1, int(min_items)):
        raise RuntimeError(f"今日热榜仅返回 {len(items)} 条有效数据")
    return items
