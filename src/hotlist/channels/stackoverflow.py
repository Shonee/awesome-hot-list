"""Stack Overflow hot questions adapter using the public Stack Exchange API."""

import html
import time
from urllib.parse import urlencode

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


API_URL = "https://api.stackexchange.com/2.3/questions"
SOURCE_URL = "https://stackoverflow.com/questions?tab=hot"
REQUEST_PARAMS = {
    "order": "desc",
    "sort": "hot",
    "site": "stackoverflow",
    "pagesize": "50",
    "filter": "default",
}


def _published_at(timestamp) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(timestamp)))
    except (TypeError, ValueError, OverflowError):
        return ""


def parse_questions(payload: dict) -> list[HotItem]:
    """Normalize Stack Exchange question records into the common hot-item model."""
    items = []
    seen = set()
    for row in (payload or {}).get("items", []):
        if not isinstance(row, dict):
            continue
        title = html.unescape(str(row.get("title") or "")).strip()
        url = str(row.get("link") or "").strip()
        if not title or not url or title in seen:
            continue
        seen.add(title)
        score = row.get("score")
        answers = row.get("answer_count")
        views = row.get("view_count")
        details = []
        if answers is not None:
            details.append(f"{answers} 个回答")
        if views is not None:
            details.append(f"{views} 次浏览")
        items.append(
            HotItem(
                rank=len(items) + 1,
                title=title,
                url=url,
                hot=score,
                description=" · ".join(details),
                published_at=_published_at(row.get("creation_date")),
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    query = urlencode(REQUEST_PARAMS)
    payload = get(f"{API_URL}?{query}", res_type="json", headers={"Accept": "application/json"})
    return snapshot("stackoverflow", [Ranking("hot", "热门问题", parse_questions(payload), SOURCE_URL)])
