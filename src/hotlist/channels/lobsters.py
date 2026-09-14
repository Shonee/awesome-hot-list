"""Lobsters official hottest JSON adapter."""

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://lobste.rs/"
API_URL = "https://lobste.rs/hottest.json"


def parse_hottest(payload: list) -> list[HotItem]:
    items = []
    for row in payload or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or row.get("short_id_url") or "").strip()
        if not title or not url:
            continue
        tags = ", ".join(row.get("tags") or [])
        comments = f"{row.get('comment_count', 0)} comments"
        items.append(
            HotItem(
                len(items) + 1,
                title,
                url,
                hot=row.get("score"),
                description=" · ".join(filter(None, (comments, tags))),
                published_at=row.get("created_at") or "",
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_hottest(get(API_URL, res_type="json", timeout=20, retries=2))
    return snapshot(
        "lobsters",
        [Ranking("hottest", "Hottest", items, SOURCE_URL, "Lobsters 官方 API", API_URL)],
    )
