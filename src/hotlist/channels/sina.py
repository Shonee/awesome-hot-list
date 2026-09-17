"""Sina News and Finance official ranking adapter."""

import json
import logging

from src.utils.http_utils import get
from src.utils.time_utils import project_now

from ..models import HotItem, Ranking
from .common import clean_html, select_live_items, snapshot


SOURCE_URL = "https://news.sina.com.cn/"
NEWS_API_URL = "https://top.news.sina.com.cn/ws/GetTopDataList.php"
FINANCE_API_URL = "https://top.finance.sina.com.cn/ws/GetTopDataList.php"
LIVE_API_URL = "https://app.cj.sina.com.cn/api/news/pc?page=1&size=200&tag=0"
LIVE_SOURCE_URL = "https://finance.sina.com.cn/7x24/"
CATEGORIES = (
    ("news", "新闻热榜", "www_www_all_suda_suda", SOURCE_URL, NEWS_API_URL),
    ("finance", "财经热榜", "finance_0_suda", "https://finance.sina.com.cn/", FINANCE_API_URL),
)
logger = logging.getLogger(__name__)


def _number(value):
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_top_data(body: str) -> list[HotItem]:
    start = (body or "").find("{")
    if start < 0:
        return []
    try:
        payload, _ = json.JSONDecoder().raw_decode(body[start:])
    except json.JSONDecodeError:
        return []
    items = []
    seen = set()
    for row in payload.get("data") or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)
        items.append(
            HotItem(
                len(items) + 1,
                title,
                url,
                hot=_number(row.get("top_num")),
                description=row.get("media") or "",
                published_at=row.get("time") or "",
            )
        )
        if len(items) >= 50:
            break
    return items


def parse_live_payload(payload: dict) -> list[HotItem]:
    rows = payload.get("result", {}).get("data", {}).get("feed", {}).get("list", []) if isinstance(payload, dict) else []
    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = clean_html(row.get("rich_text"))
        item_id = row.get("id")
        url = str(row.get("docurl") or (f"https://wap.cj.sina.cn/pc/7x24/{item_id}" if item_id else "")).strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url, published_at=row.get("create_time") or ""))
    return items


def _ranking_url(api_url: str, category: str) -> str:
    date = project_now().strftime("%Y%m%d")
    return (
        f"{api_url}?top_type=day&top_cat={category}&top_time={date}"
        "&top_show_num=20&top_order=DESC"
    )


def collect_live() -> "ChannelSnapshot":
    payload = get(LIVE_API_URL, res_type="json", timeout=20, retries=1)
    live_items = select_live_items(parse_live_payload(payload))
    return snapshot(
        "sina",
        [Ranking("live", "7x24", live_items, LIVE_SOURCE_URL, "新浪官方", LIVE_API_URL, "live")],
    )


def collect() -> "ChannelSnapshot":
    rankings = []
    warnings = []
    for ranking_id, name, category, source_url, api_url in CATEGORIES:
        request_url = _ranking_url(api_url, category)
        items = parse_top_data(get(request_url, timeout=20, retries=2))
        rankings.append(Ranking(ranking_id, name, items, source_url, "新浪官方", request_url))
    try:
        live_ranking = collect_live().rankings[0]
    except Exception as exc:  # noqa: BLE001 - one live ranking must not hide the hot rankings
        logger.warning("新浪 7x24 请求失败: %s", exc)
        live_ranking = Ranking("live", "7x24", [], LIVE_SOURCE_URL, "新浪官方", LIVE_API_URL, "live")
        warnings.append("7x24")
    rankings.append(live_ranking)
    result = snapshot("sina", rankings)
    result.warnings = warnings
    return result
