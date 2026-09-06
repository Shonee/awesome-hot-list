"""Zhihu hot search and hot list adapter."""

import logging
import os
from urllib.parse import quote

from bs4 import BeautifulSoup

from src.utils.http_utils import get
from src.utils.time_utils import project_now, timestamp_string

from ..models import HotItem, Ranking
from .common import snapshot
from .tophub import fetch_ranking as fetch_tophub_ranking


SEARCH_URL = "https://www.zhihu.com/topsearch"
HOT_API = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
HOT_PAGE_URL = "https://www.zhihu.com/hot"
TOPHUB_HOT_URL = "https://tophub.today/n/mproPpoq6O"


logger = logging.getLogger(__name__)


def _headers() -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    }
    cookie = os.environ.get("ZHIHU_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie
    return headers


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
                published_at=timestamp_string(target.get("created") or project_now().timestamp()),
            )
        )
    return items


def collect() -> "ChannelSnapshot":
    headers = _headers()
    rankings = []
    try:
        search_items = parse_hot_search(get(SEARCH_URL, headers=headers))
    except Exception as exc:  # noqa: BLE001 - the hot list can still keep this channel usable
        logger.warning("知乎热搜请求失败: %s", exc)
        search_items = []
    if search_items:
        rankings.append(
            Ranking(
                "search",
                "知乎热搜",
                search_items,
                SEARCH_URL,
                provider_name="知乎官方",
                provider_url=SEARCH_URL,
            )
        )

    hot_items = []
    provider_name = ""
    provider_url = ""
    if os.environ.get("ZHIHU_COOKIE", "").strip():
        try:
            hot_items = parse_hot_list(get(HOT_API, res_type="json", headers=headers))
            if not hot_items:
                raise RuntimeError("official API returned no usable items")
            provider_name = "知乎官方"
            provider_url = HOT_API
        except Exception as exc:  # noqa: BLE001 - TodayHot is the explicit fallback
            logger.warning("知乎官方热榜请求失败，尝试今日热榜: %s", exc)

    if not hot_items:
        hot_items = fetch_tophub_ranking(
            TOPHUB_HOT_URL,
            allowed_hosts=("zhihu.com",),
            limit=50,
            min_items=5,
        )
        provider_name = "今日热榜"
        provider_url = TOPHUB_HOT_URL

    rankings.append(
        Ranking(
            "hot",
            "知乎热榜",
            hot_items,
            HOT_PAGE_URL,
            provider_name=provider_name,
            provider_url=provider_url,
        )
    )
    return snapshot(
        "zhihu",
        rankings,
    )
