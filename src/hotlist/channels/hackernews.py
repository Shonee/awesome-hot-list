"""Hacker News official Firebase API adapter."""

from datetime import datetime, timezone
import logging

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://news.ycombinator.com/"
TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
DETAIL_LIMIT = 25
OUTPUT_LIMIT = 20
logger = logging.getLogger(__name__)


def parse_story(row: dict, rank: int):
    if not isinstance(row, dict) or row.get("type") != "story" or row.get("deleted") or row.get("dead"):
        return None
    title = str(row.get("title") or "").strip()
    story_id = row.get("id")
    if not title or not story_id:
        return None
    published = ""
    if isinstance(row.get("time"), (int, float)):
        published = datetime.fromtimestamp(row["time"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return HotItem(
        rank,
        title,
        row.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
        hot=row.get("score"),
        description=f"{row.get('descendants', 0)} comments",
        published_at=published,
    )


def collect() -> "ChannelSnapshot":
    story_ids = get(TOP_STORIES_URL, res_type="json", timeout=20, retries=2)
    items = []
    failed_details = 0
    for story_id in list(story_ids or [])[:DETAIL_LIMIT]:
        try:
            row = get(ITEM_URL.format(story_id=story_id), res_type="json", timeout=12, retries=1)
        except Exception as exc:  # noqa: BLE001 - one missing story must not drop the ranking
            failed_details += 1
            logger.warning("Hacker News 条目请求失败: id=%s: %s", story_id, exc)
            continue
        item = parse_story(row, len(items) + 1)
        if item:
            items.append(item)
        if len(items) >= OUTPUT_LIMIT:
            break
    result = snapshot(
        "hackernews",
        [Ranking("top", "Top Stories", items, SOURCE_URL, "Hacker News 官方 API", TOP_STORIES_URL)],
    )
    if failed_details:
        result.warnings.append(f"{failed_details} 个 Hacker News 条目请求失败")
    return result
