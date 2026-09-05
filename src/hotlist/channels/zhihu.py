"""Zhihu hot search and hot list adapter."""

import os
import time
from urllib.parse import quote

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot, unavailable


SEARCH_URL = "https://www.zhihu.com/topsearch"
HOT_API = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"


def _headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Cookie": os.environ.get("ZHIHU_COOKIE", ""),
    }


def parse_hot_search(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for index, node in enumerate(soup.find_all("div", class_="TopSearchMain-item"), 1):
        title_node = node.find("div", class_="TopSearchMain-title")
        if not title_node:
            continue
        title = title_node.get_text(strip=True)
        items.append(HotItem(index, title, f"https://www.zhihu.com/search?q={quote(title)}"))
    return items


def parse_hot_list(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("data", []), 1):
        target = row.get("target") or {}
        title = target.get("title")
        if not title or not target.get("id"):
            continue
        children = row.get("children") or []
        items.append(
            HotItem(
                index,
                title,
                f"https://www.zhihu.com/question/{target['id']}",
                hot=row.get("detail_text"),
                description=target.get("excerpt") or "",
                image_url=children[0].get("thumbnail", "") if children else "",
                published_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(target.get("created") or time.time())),
            )
        )
    return items


def collect() -> "ChannelSnapshot":
    if not os.environ.get("ZHIHU_COOKIE", "").strip():
        return unavailable("zhihu", "missing ZHIHU_COOKIE")
    headers = _headers()
    return snapshot(
        "zhihu",
        [
            Ranking("search", "知乎热搜", parse_hot_search(get(SEARCH_URL, headers=headers)), SEARCH_URL),
            Ranking("hot", "知乎热榜", parse_hot_list(get(HOT_API, res_type="json", headers=headers)), "https://www.zhihu.com/hot"),
        ],
    )
