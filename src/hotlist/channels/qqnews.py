"""Tencent News homepage article adapter."""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://news.qq.com/"


def parse_news(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select("a[href]"):
        url = urljoin(SOURCE_URL, link.get("href", ""))
        title = link.get_text(" ", strip=True)
        if not title or len(title) < 6 or "news.qq.com" not in url or url in seen:
            continue
        if any(word in title for word in ("下载", "客户端", "广告", "登录")):
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    return snapshot("qqnews", [Ranking("latest", "实时资讯", parse_news(get(SOURCE_URL)), SOURCE_URL)])
