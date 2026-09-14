"""Baidu realtime hot-search adapter."""

import json
import re

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://top.baidu.com/board?tab=realtime"
_DATA_PATTERN = re.compile(r"<!--s-data:(.*?)-->", re.DOTALL)


def _number(value):
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_hot_list(html: str) -> list[HotItem]:
    match = _DATA_PATTERN.search(html or "")
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    cards = (payload.get("data") or {}).get("cards") or []
    rows = next(
        (card.get("content") or [] for card in cards if card.get("component") == "hotList"),
        [],
    )
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("word") or row.get("query") or "").strip()
        url = str(row.get("url") or row.get("rawUrl") or row.get("appUrl") or "").strip()
        if not title or not url:
            continue
        items.append(
            HotItem(
                len(items) + 1,
                title,
                url,
                hot=_number(row.get("hotScore")),
                description=row.get("desc") or "",
                image_url=row.get("img") or "",
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_hot_list(get(SOURCE_URL, timeout=20, retries=2))
    return snapshot(
        "baidu",
        [Ranking("realtime", "实时热搜", items, SOURCE_URL, "百度官方", SOURCE_URL)],
    )
