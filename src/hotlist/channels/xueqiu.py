"""Xueqiu hot topic adapter."""

import requests

from ..models import HotItem, Ranking
from .common import snapshot


API_URL = "https://xueqiu.com/hot_event/list.json?count=10"
SOURCE_URL = "https://xueqiu.com/today"


def parse_topics(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("list", []), 1):
        title = str(row.get("tag") or row.get("title") or "").strip().strip("#").strip()
        if not title:
            continue
        item_id = row.get("id")
        url = f"https://xueqiu.com/hot_event/{item_id}" if item_id else SOURCE_URL
        items.append(HotItem(index, title, url, hot=row.get("status_count") or row.get("hot"), description=row.get("content") or ""))
    return items


def collect() -> "ChannelSnapshot":
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://xueqiu.com/"}
    session.get("https://xueqiu.com/", headers=headers, timeout=15).raise_for_status()
    response = session.get(API_URL, headers={**headers, "X-Requested-With": "XMLHttpRequest"}, timeout=15)
    response.raise_for_status()
    return snapshot("xueqiu", [Ranking("hot", "热门话题", parse_topics(response.json()), SOURCE_URL)])
