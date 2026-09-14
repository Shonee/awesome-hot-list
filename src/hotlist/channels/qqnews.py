"""Tencent News hot-ranking adapter with a TodayHot fallback."""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot
from .tophub import fetch_ranking as fetch_tophub_ranking


SOURCE_URL = "https://news.qq.com/"
API_URL = "https://r.inews.qq.com/gw/event/pc_hot_ranking_list?page_size=20"
TOPHUB_URL = "https://tophub.today/n/12owgX0oNV"


logger = logging.getLogger(__name__)


def parse_news(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select("a[href]"):
        url = urljoin(SOURCE_URL, link.get("href", ""))
        title = link.get_text(" ", strip=True)
        if not title or len(title) < 6 or "news.qq.com" not in url or url in seen:
            continue
        if any(word in title for word in ("下载", "客户端", "广告", "登录")):
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 50:
            break
    return items


def parse_hot_ranking(payload: dict) -> list[HotItem]:
    """Normalize the official Tencent News PC hot-ranking response."""
    if not isinstance(payload, dict) or payload.get("ret", 0) != 0:
        return []
    id_lists = payload.get("idlist") or []
    if not id_lists or not isinstance(id_lists[0], dict):
        return []

    items = []
    seen = set()
    for fallback_rank, row in enumerate(id_lists[0].get("newslist") or [], 1):
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or row.get("surl") or row.get("short_url") or "").strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)
        event = row.get("hotEvent") if isinstance(row.get("hotEvent"), dict) else {}
        rank = event.get("ranking") or row.get("ranking") or fallback_rank
        items.append(
            HotItem(
                rank,
                title,
                url,
                hot=event.get("hotScore"),
                description=row.get("abstract") or row.get("nlpAbstract") or "",
                published_at=row.get("time") or "",
            )
        )
    return items


def collect() -> "ChannelSnapshot":
    items = []
    provider_name = ""
    provider_url = ""
    try:
        items = parse_hot_ranking(get(API_URL, res_type="json"))
        if not items:
            raise RuntimeError("official API returned no usable items")
        provider_name = "腾讯新闻官方"
        provider_url = API_URL
    except Exception as official_error:  # noqa: BLE001 - TodayHot is the explicit fallback
        logger.warning("腾讯新闻官方热榜请求失败，尝试今日热榜: %s", official_error)
        try:
            items = fetch_tophub_ranking(
                TOPHUB_URL,
                allowed_hosts=("qq.com",),
                limit=50,
                min_items=5,
            )
        except Exception as fallback_error:  # noqa: BLE001 - expose complete source failure to runner
            raise RuntimeError(
                f"腾讯新闻官方及今日热榜数据源均不可用: {fallback_error}"
            ) from fallback_error
        provider_name = "今日热榜"
        provider_url = TOPHUB_URL

    return snapshot(
        "qqnews",
        [
            Ranking(
                "latest",
                "热点榜",
                items,
                SOURCE_URL,
                provider_name=provider_name,
                provider_url=provider_url,
            )
        ],
    )
