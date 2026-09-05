"""36Kr hot ranking adapter."""

import time

from src.utils.http_utils import post

from ..models import HotItem, Ranking
from .common import snapshot


API_URL = "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot"
SOURCE_URL = "https://www.36kr.com/hot-list/catalog"


def parse_hot(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("data", {}).get("hotRankList", []), 1):
        material = row.get("templateMaterial") or {}
        title = material.get("widgetTitle") or row.get("title")
        item_id = row.get("itemId")
        if title and item_id:
            items.append(HotItem(index, title, f"https://www.36kr.com/p/{item_id}", hot=material.get("statRead") or material.get("hotScore"), description=material.get("summary") or "", image_url=material.get("widgetImage") or ""))
    return items


def collect() -> "ChannelSnapshot":
    payload = post(
        API_URL,
        payload={
            "partner_id": "wap",
            "param": {"siteId": 1, "platformId": 2},
            "timestamp": int(time.time() * 1000),
        },
        res_type="json",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    return snapshot("36kr", [Ranking("hot", "热榜", parse_hot(payload), SOURCE_URL)])
