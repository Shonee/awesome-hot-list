"""Jandan 4-hour hot ranking, mostly image posts with a pinned hot comment."""

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import clean_html, snapshot


API_URL = "https://jandan.net/api/top/4hr"
SOURCE_URL = "https://jandan.net/top#tab=4hr"
TOPIC_PREFIX = "https://jandan.net/t/"
ITEM_LIMIT = 50


def _title(value) -> str:
    # Posts and hot comments carry their own line breaks; cards want one line.
    return " ".join(clean_html(value).split())


def parse_rank(payload: dict) -> list[HotItem]:
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise RuntimeError(f"jandan returned an unusable payload: {str(payload)[:120]}")

    candidates = []
    seen = set()
    for row in payload.get("data") or []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("id") or "").strip()
        title = _title(row.get("content"))
        if not title:
            hot_tucao = row.get("hot_tucao")
            title = _title(hot_tucao.get("content")) if isinstance(hot_tucao, dict) else ""
        if not title or item_id in seen:
            continue
        seen.add(item_id)
        candidates.append((row, title))

    # The endpoint returns the newest posts first, unlike the other /top tabs.
    candidates.sort(key=lambda pair: -int(pair[0].get("vote_positive") or 0))
    return [
        HotItem(
            rank,
            title,
            f"{TOPIC_PREFIX}{row.get('id')}",
            hot=row.get("vote_positive"),
            published_at=str(row.get("date_gmt") or ""),
        )
        for rank, (row, title) in enumerate(candidates[:ITEM_LIMIT], 1)
    ]


def collect() -> "ChannelSnapshot":
    return snapshot(
        "jandan",
        [Ranking("4hr", "4小时热门", parse_rank(get(API_URL, res_type="json")), SOURCE_URL, "煎蛋官方", SOURCE_URL)],
    )
