"""Trending on Bing topics from the public Bing News page (US locale)."""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.bing.com/news?cc=us&setlang=en-US"


def parse_trending(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select(".TrendingOnBing a[href*='/news/topicview']"):
        title = link.get_text(" ", strip=True)
        url = urljoin("https://www.bing.com/", link.get("href", ""))
        if not title or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 30:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_trending(get(SOURCE_URL, timeout=12, retries=1))
    return snapshot("bing", [Ranking("trending-news", "Trending on Bing（美国新闻）", items, SOURCE_URL)])
