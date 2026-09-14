"""Xueqiu hot topic adapter."""

import logging

import requests

from ..models import HotItem, Ranking
from .common import snapshot
from .tophub import fetch_ranking as fetch_tophub_ranking


API_URL = "https://xueqiu.com/hot_event/list.json?count=10"
SOURCE_URL = "https://xueqiu.com/today"
TOPHUB_URL = "https://tophub.today/n/X12owXzvNV"


logger = logging.getLogger(__name__)


def parse_topics(payload: dict) -> list[HotItem]:
    items = []
    for index, row in enumerate((payload or {}).get("list", []), 1):
        title = str(row.get("tag") or row.get("title") or "").strip().strip("#").strip()
        if not title:
            continue
        item_id = row.get("id")
        url = f"https://xueqiu.com/hot_event/{item_id}" if item_id else SOURCE_URL
        items.append(HotItem(index, title, url, hot=row.get("status_count") or row.get("hot"), description=row.get("content") or ""))
    return items


def fetch_official_topics() -> list[HotItem]:
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://xueqiu.com/"}
    session.get("https://xueqiu.com/", headers=headers, timeout=15).raise_for_status()
    response = session.get(
        API_URL,
        headers={**headers, "X-Requested-With": "XMLHttpRequest"},
        timeout=15,
    )
    response.raise_for_status()
    return parse_topics(response.json())


def collect() -> "ChannelSnapshot":
    topics = []
    provider_name = ""
    provider_url = ""
    try:
        topics = fetch_official_topics()
        if not topics:
            raise RuntimeError("official API returned no usable items")
        provider_name = "雪球官方"
        provider_url = API_URL
    except Exception as official_error:  # noqa: BLE001 - TodayHot is the explicit fallback
        logger.warning("雪球官方热榜请求失败，尝试今日热榜: %s", official_error)
        try:
            topics = fetch_tophub_ranking(
                TOPHUB_URL,
                allowed_hosts=("xueqiu.com",),
                limit=50,
                min_items=5,
            )
        except Exception as fallback_error:  # noqa: BLE001 - expose complete source failure to runner
            raise RuntimeError(
                f"雪球官方及今日热榜数据源均不可用: {fallback_error}"
            ) from fallback_error
        provider_name = "今日热榜"
        provider_url = TOPHUB_URL

    return snapshot(
        "xueqiu",
        [
            Ranking(
                "hot",
                "热门话题",
                topics,
                SOURCE_URL,
                provider_name=provider_name,
                provider_url=provider_url,
            )
        ],
    )
