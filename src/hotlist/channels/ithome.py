"""IT Home's official daily most-read ranking."""

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.ithome.com/"


def parse_daily_rank(html: str | bytes) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select("#rank #d-1 > li a[href]"):
        title = link.get("title") or link.get_text(" ", strip=True)
        url = link.get("href", "")
        if not title or (urlparse(url).hostname or "").lower() != "www.ithome.com" or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 30:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_daily_rank(get(SOURCE_URL, res_type="bytes", timeout=20, retries=1))
    return snapshot("ithome", [Ranking("daily", "日榜", items, SOURCE_URL, "IT之家官方", SOURCE_URL)])
