"""Bilibili hot search and video rankings."""

from urllib.parse import quote

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SEARCH_API = "https://app.bilibili.com/x/v2/search/trending/ranking"
POPULAR_API = "https://api.bilibili.com/x/web-interface/popular?ps=50&pn=1"
RANKING_API = "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"


def parse_hot_search(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("data", {}).get("list", []), 1):
        title = row.get("keyword") or row.get("show_name")
        if title:
            items.append(
                HotItem(
                    index,
                    title,
                    f"https://search.bilibili.com/all?keyword={quote(title)}",
                    description=row.get("show_name") or "",
                )
            )
    return items


def parse_videos(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("data", {}).get("list", []), 1):
        title = row.get("title")
        if not title:
            continue
        stat = row.get("stat") or {}
        url = row.get("short_link_v2") or row.get("short_link")
        if not url and row.get("bvid"):
            url = f"https://www.bilibili.com/video/{row['bvid']}"
        items.append(
            HotItem(
                index,
                title,
                url or "https://www.bilibili.com/v/popular/all",
                hot=stat.get("view"),
                description=row.get("desc") or "",
                image_url=row.get("pic") or "",
                published_at=str(row.get("pubdate") or ""),
            )
        )
    return items


def collect() -> "ChannelSnapshot":
    return snapshot(
        "bilibili",
        [
            Ranking("search", "热门搜索", parse_hot_search(get(SEARCH_API, res_type="json")), "https://search.bilibili.com/all"),
            Ranking("popular", "全站热门视频", parse_videos(get(POPULAR_API, res_type="json")), "https://www.bilibili.com/v/popular/all"),
            Ranking("ranking", "视频排行榜", parse_videos(get(RANKING_API, res_type="json")), "https://www.bilibili.com/v/popular/rank/all"),
        ],
    )
