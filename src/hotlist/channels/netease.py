"""NetEase News official hot-flow adapter."""

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


API_URL = "https://m.163.com/fe/api/hot/news/flow"
SOURCE_URL = "https://news.163.com/"


def parse_news_flow(payload: dict) -> list[HotItem]:
    if not isinstance(payload, dict) or payload.get("code") != 200:
        return []
    items = []
    seen = set()
    for row in ((payload.get("data") or {}).get("list") or []):
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)
        items.append(
            HotItem(
                len(items) + 1,
                title,
                url,
                description=row.get("source") or "",
                image_url=row.get("imgsrc") or row.get("recImgsrc") or "",
                published_at=row.get("publishTime") or row.get("ptime") or "",
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_news_flow(get(API_URL, res_type="json", timeout=20, retries=2))
    return snapshot(
        "netease",
        [Ranking("hot", "热门新闻", items, SOURCE_URL, "网易新闻官方", API_URL)],
    )
