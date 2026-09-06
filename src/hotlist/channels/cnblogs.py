"""Cnblogs 24-hour recommended article adapter."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.cnblogs.com/aggsite/topdigged24h"


def _recommend_count(value: str):
    match = re.search(r"推荐\s*(\d+)", value or "")
    return int(match.group(1)) if match else None


def parse_rank(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("a.post-item-title[href], a[href*='/p/']")
    items = []
    seen = set()
    for link in links:
        title = link.get_text(" ", strip=True)
        url = urljoin("https://www.cnblogs.com/", link.get("href", ""))
        if not title or "/p/" not in url or url in seen:
            continue
        seen.add(url)
        parent = link.parent.parent if link.parent else link
        context = parent.get_text(" ", strip=True) if parent else ""
        items.append(HotItem(len(items) + 1, title, url, hot=_recommend_count(context)))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_rank(get(SOURCE_URL))
    return snapshot("cnblogs", [Ranking("recommended-24h", "24 小时推荐排行", items, SOURCE_URL)])
