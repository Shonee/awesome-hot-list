"""Douyin hot search adapter."""

from datetime import datetime
from urllib.parse import quote

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


API_URL = "https://aweme-lq.snssdk.com/aweme/v1/hot/search/list/"


def extract_cover_url(word_cover) -> str:
    if not isinstance(word_cover, dict):
        return ""
    urls = word_cover.get("url_list")
    return urls[0] or "" if isinstance(urls, list) and urls else ""


def parse_hot_search(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("data", {}).get("word_list", []), 1):
        title = row.get("word") or "Unknown"
        event_time = row.get("event_time")
        published_at = ""
        if event_time:
            published_at = datetime.fromtimestamp(event_time).strftime("%Y-%m-%d %H:%M:%S")
        items.append(
            HotItem(
                index,
                title,
                f"https://www.douyin.com/search/{quote(title)}",
                hot=row.get("hot_value"),
                image_url=extract_cover_url(row.get("word_cover")),
                published_at=published_at,
            )
        )
    return items


def collect() -> "ChannelSnapshot":
    return snapshot(
        "douyin",
        [Ranking("hot", "热搜", parse_hot_search(get(API_URL, res_type="json")), "https://www.douyin.com/hot")],
    )
