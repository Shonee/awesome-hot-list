"""Gamersky's ranked hot-news sidebar, separate from its latest-news feed."""

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import same_host, snapshot


SOURCE_URL = "https://www.gamersky.com/news/"


def parse_hot_news(html: str | bytes) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for row in soup.select(".Mid2_R .Mid2Rtxt > li"):
        link = row.select_one("a[href]")
        if not link:
            continue
        title = link.get("title") or link.get_text(" ", strip=True)
        url = link.get("href", "")
        if not title or not same_host(url, {"www.gamersky.com"}) or url in seen:
            continue
        seen.add(url)
        rank_node = row.select_one(".num")
        rank = rank_node.get_text(strip=True) if rank_node else ""
        items.append(HotItem(int(rank) if rank.isdigit() else len(items) + 1, title, url))
        if len(items) >= 30:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_hot_news(get(SOURCE_URL, res_type="bytes", timeout=20, retries=1))
    return snapshot("gamersky", [Ranking("hot-news", "热点资讯排行", items, SOURCE_URL, "游民星空官方", SOURCE_URL)])
