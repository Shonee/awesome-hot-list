"""Douban group topic adapter."""

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import clean_html, snapshot


SOURCE_URL = "https://www.douban.com/group/explore"


def parse_topics(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for index, row in enumerate(soup.select("div.channel-item"), 1):
        link = row.select_one("h3 a[href]")
        if link:
            items.append(HotItem(index, link.get_text(" ", strip=True), link.get("href", ""), description=clean_html(row.select_one("div.content"))))
    return items


def collect() -> "ChannelSnapshot":
    return snapshot("douban", [Ranking("group", "小组精选", parse_topics(get(SOURCE_URL)), SOURCE_URL)])
