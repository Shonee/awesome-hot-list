"""Baidu Tieba hot-topic adapter."""

import time
from html import unescape
from urllib.parse import urljoin

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


HOMEPAGE_URL = "https://tieba.baidu.com/"
API_URL = "https://tieba.baidu.com/hottopic/browse/topicList"


def _published_at(value) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(value)))
    except (TypeError, ValueError, OverflowError):
        return str(value or "")


def parse_topics(payload: dict) -> list[HotItem]:
    data = payload.get("data") if isinstance(payload, dict) else []
    if isinstance(data, dict):
        bang_topic = data.get("bang_topic")
        if isinstance(bang_topic, dict):
            data = bang_topic.get("topic_list") or []
        else:
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
        rank = row.get("idx_num")
        if not isinstance(rank, int) or rank < 1:
            rank = len(items) + 1
        items.append(HotItem(
            rank,
            title,
            urljoin(HOMEPAGE_URL, unescape(str(url))),
            hot=row.get("discuss_num") or row.get("discussion_num"),
            description=row.get("abstract") or row.get("topic_desc") or "",
            published_at=_published_at(row.get("create_time")),
        ))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    payload = get(API_URL, res_type="json", headers={"Accept": "application/json"})
    return snapshot("tieba", [Ranking("topics", "最有料热点", parse_topics(payload), HOMEPAGE_URL)])
