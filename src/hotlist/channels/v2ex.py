"""V2EX hot topics adapter using its public hot-topics endpoint."""

import time
from urllib.parse import urljoin

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


API_URLS = (
    "https://www.v2ex.com/api/topics/hot.json",
    "https://v2ex.com/api/topics/hot.json",
)
SOURCE_URL = "https://www.v2ex.com/?tab=hot"


def _published_at(timestamp) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(timestamp)))
    except (TypeError, ValueError, OverflowError):
        return ""


def parse_topics(payload: list) -> list[HotItem]:
    """Normalize V2EX topic records and preserve the topic detail URL."""
    items = []
    seen = set()
    for row in payload or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        topic_id = row.get("id")
        if not title or title in seen:
            continue
        seen.add(title)
        path = row.get("url") or (f"/t/{topic_id}" if topic_id else "")
        url = urljoin("https://www.v2ex.com/", path) if path else SOURCE_URL
        node = row.get("node") or {}
        description = node.get("title") if isinstance(node, dict) else ""
        items.append(
            HotItem(
                rank=len(items) + 1,
                title=title,
                url=url or SOURCE_URL,
                hot=row.get("replies"),
                description=description or "",
                published_at=_published_at(row.get("last_modified")),
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    last_error = None
    for api_url in API_URLS:
        try:
            payload = get(api_url, res_type="json", headers={"Accept": "application/json"}, timeout=10, retries=1)
            return snapshot("v2ex", [Ranking("hot", "热门主题", parse_topics(payload), SOURCE_URL)])
        except Exception as exc:  # noqa: BLE001 - try the alternate public hostname
            last_error = exc
    raise last_error
