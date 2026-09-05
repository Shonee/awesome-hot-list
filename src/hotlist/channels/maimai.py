"""Maimai discussion adapter."""

import os
from urllib.parse import quote

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import clean_html, snapshot, unavailable


API_URL = "https://maimai.cn/web/feed/v5/feed_list?limit=50"
SOURCE_URL = "https://maimai.cn/web/gossip_list"


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def parse_discussions(payload: dict) -> list[HotItem]:
    items = []
    seen = set()
    for row in _walk_dicts(payload):
        title = row.get("title") or row.get("content") or row.get("text")
        if not isinstance(title, str):
            continue
        title = clean_html(title)
        if len(title) < 6 or title in seen:
            continue
        seen.add(title)
        item_id = row.get("id") or row.get("feedId") or row.get("gossipId")
        url = row.get("url") or (f"https://maimai.cn/web/gossip_detail?gid={quote(str(item_id))}" if item_id else SOURCE_URL)
        items.append(HotItem(len(items) + 1, title, url, hot=row.get("likeCount") or row.get("hot")))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    cookie = os.environ.get("MAIMAI_COOKIE", "").strip()
    if not cookie:
        return unavailable("maimai", "missing MAIMAI_COOKIE")
    return snapshot("maimai", [Ranking("gossip", "职场热议", parse_discussions(get(API_URL, res_type="json", headers={"Cookie": cookie, "Referer": SOURCE_URL})), SOURCE_URL)])
