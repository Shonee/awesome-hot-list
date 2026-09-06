"""Linux.do Discourse topic adapter."""

from urllib.parse import quote, urljoin

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://linux.do/top"
API_URL = "https://linux.do/top.json?period=weekly"


def _published_at(value) -> str:
    if not value:
        return ""
    text = str(value).replace("Z", "+00:00")
    return text.replace("T", " ")[:19]


def parse_topics(payload: dict) -> list[HotItem]:
    topics = (payload or {}).get("topic_list", {}).get("topics", [])
    items = []
    for row in topics:
        title = str(row.get("title") or "").strip()
        topic_id = row.get("id")
        if not title or not topic_id:
            continue
        slug = quote(str(row.get("slug") or title))
        category = row.get("category_name") or "社区"
        items.append(HotItem(
            len(items) + 1,
            title,
            urljoin("https://linux.do/", f"t/{slug}/{topic_id}"),
            hot=row.get("posts_count") or row.get("views"),
            description=category,
            published_at=_published_at(row.get("last_posted_at")),
        ))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    payload = get(API_URL, res_type="json", headers={"Accept": "application/json"}, timeout=12, retries=1)
    return snapshot("linuxdo", [Ranking("weekly", "本周热门主题", parse_topics(payload), SOURCE_URL)])
