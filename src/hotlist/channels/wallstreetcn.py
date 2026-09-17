"""WallstreetCN public 7x24 live-news adapter."""

from src.utils.http_utils import get
from src.utils.time_utils import timestamp_string

from ..models import HotItem, Ranking
from .common import clean_html, select_live_items, snapshot


SOURCE_URL = "https://wallstreetcn.com/live/global"
API_URL = "https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&client=pc&limit=200"


def _headline(row: dict) -> str:
    title = clean_html(row.get("title"))
    if title:
        return title
    content = clean_html(row.get("content_text") or row.get("content"))
    return f"{content[:117]}..." if len(content) > 120 else content


def parse_live_payload(payload: dict) -> list[HotItem]:
    rows = payload.get("data", {}).get("items", []) if isinstance(payload, dict) else []
    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = _headline(row)
        item_id = row.get("id")
        url = str(row.get("uri") or (f"https://wallstreetcn.com/livenews/{item_id}" if item_id else "")).strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)
        items.append(
            HotItem(
                len(items) + 1,
                title,
                url,
                description=clean_html(row.get("content_text")) if row.get("title") else "",
                published_at=timestamp_string(row.get("display_time")),
            )
        )
    return items


def collect() -> "ChannelSnapshot":
    items = select_live_items(parse_live_payload(get(API_URL, res_type="json", timeout=20, retries=1)))
    return snapshot("wallstreetcn", [Ranking("live", "7x24", items, SOURCE_URL, "华尔街见闻官方", API_URL, "live")])


collect_live = collect
