"""Weibo hot ranking adapter."""

from urllib.parse import quote

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


API_URL = "https://weibo.com/ajax/side/hotSearch"
SOURCE_URL = "https://s.weibo.com/top/summary"


def parse_hot(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("data", {}).get("realtime", []), 1):
        title = row.get("word") or row.get("note")
        if title:
            items.append(HotItem(index, title, f"https://s.weibo.com/weibo?q={quote(title)}&Refer=index", hot=row.get("num") or row.get("raw_hot")))
    return items


def collect() -> "ChannelSnapshot":
    payload = get(API_URL, res_type="json", headers={"Referer": "https://weibo.com/", "Accept": "application/json"})
    return snapshot("weibo", [Ranking("hot", "微博热榜", parse_hot(payload), SOURCE_URL)])
