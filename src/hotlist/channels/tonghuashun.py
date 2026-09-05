"""Tonghuashun news adapter."""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://news.10jqka.com.cn/today_list/"


def parse_news(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = (".list-con li a[href]", ".news-list li a[href]", "a.arc-title[href]", ".content-list a[href]")
    links = []
    for selector in selectors:
        links = soup.select(selector)
        if links:
            break
    items = []
    seen = set()
    for link in links:
        title = link.get("title") or link.get_text(" ", strip=True)
        if len(title) < 6 or title in seen:
            continue
        seen.add(title)
        items.append(HotItem(len(items) + 1, title, urljoin("https://news.10jqka.com.cn/", link.get("href", ""))))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    return snapshot("tonghuashun", [Ranking("today", "今日要闻", parse_news(get(SOURCE_URL)), SOURCE_URL)])
