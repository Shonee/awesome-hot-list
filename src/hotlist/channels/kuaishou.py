"""Kuaishou official hot rank with a rate-limited DailyHot fallback."""

import json
import logging
from urllib.parse import quote

from src.utils.http_utils import get

from ..models import EmptySourceError, HotItem, Ranking
from .common import snapshot
from .dailyhot import fetch_payload as fetch_dailyhot
from .tophub import fetch_ranking as fetch_tophub_ranking


SOURCE_URL = "https://www.kuaishou.com/?isHome=1&cc=CN"
DAILYHOT_URL = "https://api-hot.imsyy.top/kuaishou"
TOPHUB_URL = "https://tophub.today/n/MZd7PrPerO"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Referer": "https://www.kuaishou.com/",
}
logger = logging.getLogger(__name__)


def parse_official_page(html: str) -> list[HotItem]:
    marker = "window.__APOLLO_STATE__="
    start = (html or "").find(marker)
    if start < 0:
        return []
    try:
        state, _ = json.JSONDecoder().raw_decode(html[start + len(marker):])
    except json.JSONDecodeError:
        return []
    client = (state.get("defaultClient") or {}) if isinstance(state, dict) else {}
    root = client.get("ROOT_QUERY") or {}
    rank_ref = next((value for key, value in root.items() if key.startswith("visionHotRank(")), {})
    rank_data = client.get(rank_ref.get("id"), {}) if isinstance(rank_ref, dict) else {}
    items = []
    for fallback_rank, reference in enumerate(rank_data.get("items") or [], 1):
        if not isinstance(reference, dict):
            continue
        row = client.get(reference.get("id"), {})
        title = str(row.get("name") or row.get("id") or "").strip()
        if not title:
            continue
        photos = row.get("photoIds") or {}
        photo_ids = photos.get("json") or [] if isinstance(photos, dict) else []
        url = (
            f"https://www.kuaishou.com/short-video/{photo_ids[0]}"
            if photo_ids else f"https://www.kuaishou.com/search/video?searchKey={quote(title)}"
        )
        items.append(
            HotItem(
                fallback_rank,
                title,
                url,
                hot=row.get("hotValue") or row.get("viewCount"),
                description=row.get("tagType") or "",
                image_url=row.get("poster") or "",
            )
        )
        if len(items) >= 50:
            break
    return items


def parse_dailyhot(payload) -> list[HotItem]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    items = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or row.get("name") or "").strip()
        url = str(row.get("url") or row.get("mobileUrl") or "").strip()
        if not title or not url:
            continue
        items.append(
            HotItem(
                len(items) + 1,
                title,
                url,
                hot=row.get("hot") or row.get("hotValue"),
                description=row.get("desc") or row.get("description") or "",
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    try:
        items = parse_official_page(get(SOURCE_URL, headers=HEADERS, timeout=25, retries=2))
        if not items:
            raise RuntimeError("official page returned no usable items")
        provider_name = "快手官方"
        provider_url = SOURCE_URL
    except Exception as official_error:  # noqa: BLE001 - explicit provider fallback
        logger.warning("快手官方热榜请求失败，尝试今日热榜: %s", official_error)
        try:
            items = fetch_tophub_ranking(
                TOPHUB_URL,
                allowed_hosts=("kuaishou.com",),
                limit=50,
                min_items=5,
            )
            provider_name = "今日热榜"
            provider_url = TOPHUB_URL
        except Exception as tophub_error:  # noqa: BLE001 - final DailyHot fallback
            logger.warning("快手今日热榜请求失败，尝试 DailyHot API: %s", tophub_error)
            items = parse_dailyhot(fetch_dailyhot(DAILYHOT_URL))
            if not items:
                raise EmptySourceError("快手官方、今日热榜及 DailyHot API 均未返回有效数据")
            provider_name = "DailyHot API"
            provider_url = DAILYHOT_URL
    return snapshot(
        "kuaishou",
        [Ranking("hot", "快手热榜", items, SOURCE_URL, provider_name, provider_url)],
    )
