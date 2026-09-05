"""Hupu hot-topic adapter using the mobile SSR payload."""

import json

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://m.hupu.com/hot"


def parse_topics(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    next_data = soup.select_one("#__NEXT_DATA__")
    if next_data and next_data.string:
        payload = json.loads(next_data.string)
        rows = payload.get("props", {}).get("pageProps", {}).get("res", [])
        items = []
        for index, row in enumerate(rows, 1):
            title = row.get("tagName")
            if not title:
                continue
            tag_id = row.get("tagId")
            items.append(HotItem(row.get("rank") or index, title, f"{SOURCE_URL}?tagId={tag_id}" if tag_id else SOURCE_URL, hot=row.get("heat"), description=row.get("tagUpdateDesc") or ""))
        return items

    # Keep the parser compatible with archived desktop markup and fixtures.
    items = []
    for index, row in enumerate(soup.select("div.t-info"), 1):
        link = row.select_one("a[href]")
        title = row.select_one("span.t-title")
        if link and title:
            replies = row.select_one("span.t-replies")
            items.append(HotItem(index, title.get_text(" ", strip=True), urljoin("https://bbs.hupu.com/", link.get("href", "")), hot=replies.get_text(" ", strip=True) if replies else None))
    return items


def collect() -> "ChannelSnapshot":
    return snapshot("hupu", [Ranking("community", "步行街热帖", parse_topics(get(SOURCE_URL)), SOURCE_URL)])
