"""Hupu homepage posts and walk-street threads."""

import json
import logging

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://m.hupu.com/hot"
HOME_URL = "https://m.hupu.com/"
WALK_STREET_URL = "https://bbs.hupu.com/all-gambia"
logger = logging.getLogger(__name__)


def parse_home(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select("a.news-item[href*='/bbs/']"):
        heading = link.select_one(".news-item-info-title")
        title = heading.get_text(" ", strip=True) if heading else ""
        url = urljoin(HOME_URL, link.get("href", ""))
        if not title or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 50:
            break
    return items


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
    rankings = [Ranking("home", "虎扑首页", parse_home(get(HOME_URL)), HOME_URL)]
    try:
        walk_items = parse_topics(get(WALK_STREET_URL, timeout=12, retries=1))
        if walk_items:
            rankings.append(Ranking("walk-street", "步行街热帖", walk_items, WALK_STREET_URL))
    except Exception as exc:  # noqa: BLE001 - the main Hupu board remains useful
        logger.warning("虎扑步行街请求失败: %s", exc)
    return snapshot("hupu", rankings)
