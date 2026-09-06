"""Baidu Tieba hot-topic adapter."""

import time
from urllib.parse import urljoin

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://tieba.baidu.com/hottopic/browse/topicList"


def _published_at(value) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(value)))
    except (TypeError, ValueError, OverflowError):
        return str(value or "")


def parse_topics(payload: dict) -> list[HotItem]:
    data = payload.get("data") if isinstance(payload, dict) else []
    if isinstance(data, dict):
        data = data.get("topic_list") or data.get("topics") or data.get("list") or []
    items = []
    seen = set()
    for row in data or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("topic_name") or row.get("name") or "").strip()
        url = row.get("topic_url") or row.get("url") or ""
        if not title or title in seen:
            continue
        seen.add(title)
        items.append(HotItem(
            len(items) + 1,
            title,
            urljoin("https://tieba.baidu.com/", str(url)),
            hot=row.get("discuss_num") or row.get("discussion_num"),
            published_at=_published_at(row.get("create_time")),
        ))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    payload = get(SOURCE_URL, res_type="json", headers={"Accept": "application/json"})
    return snapshot("tieba", [Ranking("topics", "热议话题", parse_topics(payload), SOURCE_URL)])
