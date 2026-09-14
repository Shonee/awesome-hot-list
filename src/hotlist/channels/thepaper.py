"""The Paper official hot-news adapter."""

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.thepaper.cn/"
API_URL = "https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar"


def _number(value) -> int:
    try:
        return int(str(value or "0").replace(",", ""))
    except ValueError:
        return 0


def parse_hot_news(payload: dict) -> list[HotItem]:
    rows = ((payload or {}).get("data") or {}).get("hotNews") or []
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        content_id = str(row.get("contId") or "").strip()
        title = str(row.get("name") or "").strip()
        if not content_id or not title:
            continue
        items.append(
            HotItem(
                len(items) + 1,
                title,
                f"https://www.thepaper.cn/newsDetail_forward_{content_id}",
                hot=_number(row.get("praiseTimes")) + _number(row.get("interactionNum")),
                description=(row.get("nodeInfo") or {}).get("name") or "",
                image_url=row.get("pic") or "",
                published_at=row.get("pubTime") or "",
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_hot_news(get(API_URL, res_type="json", timeout=20, retries=2))
    return snapshot(
        "thepaper",
        [Ranking("hot", "热新闻", items, SOURCE_URL, "澎湃新闻官方", API_URL)],
    )
