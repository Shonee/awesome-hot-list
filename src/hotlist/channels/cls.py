"""Cailian Press hot-news adapter using the homepage SSR payload."""

import json
import time

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.cls.cn/telegraph"
DETAIL_URL = "https://www.cls.cn/detail/{}"


def _published_at(timestamp) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(timestamp)))
    except (TypeError, ValueError, OverflowError):
        return ""


def _next_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("script#__NEXT_DATA__")
    if not script:
        return {}
    try:
        return json.loads(script.get_text())
    except json.JSONDecodeError:
        return {}


def parse_hot_articles(html: str) -> list[HotItem]:
    """Read the current homepage's serialized hot-article list."""
    payload = _next_data(html)
    rows = payload.get("props", {}).get("pageProps", {}).get("hotArticleData", [])
    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        article_id = row.get("id")
        if not title or not article_id or title in seen:
            continue
        seen.add(title)
        items.append(
            HotItem(
                rank=len(items) + 1,
                title=title,
                url=DETAIL_URL.format(article_id),
                hot=row.get("readNum"),
                description=str(row.get("brief") or "").strip(),
                image_url=str(row.get("img") or "").strip(),
                published_at=_published_at(row.get("ctime")),
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    html = get("https://www.cls.cn/")
    return snapshot("cls", [Ranking("hot", "热门快讯", parse_hot_articles(html), SOURCE_URL)])
