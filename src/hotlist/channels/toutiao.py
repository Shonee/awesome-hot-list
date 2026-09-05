"""Toutiao hot board adapter."""

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


API_URL = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
SOURCE_URL = "https://www.toutiao.com/hot-event/hot-board/"


def parse_hot(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("data", []), 1):
        title = row.get("Title") or row.get("title")
        if title:
            image = row.get("Image") if isinstance(row.get("Image"), dict) else {}
            items.append(HotItem(index, title, row.get("Url") or row.get("url") or SOURCE_URL, hot=row.get("HotValue") if row.get("HotValue") is not None else row.get("hot"), image_url=image.get("url", "")))
    return items


def collect() -> "ChannelSnapshot":
    return snapshot("toutiao", [Ranking("hot", "热点榜", parse_hot(get(API_URL, res_type="json", headers={"Referer": "https://www.toutiao.com/"})), SOURCE_URL)])
