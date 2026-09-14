"""Sina News and Finance official ranking adapter."""

import json

from src.utils.http_utils import get
from src.utils.time_utils import project_now

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://news.sina.com.cn/"
NEWS_API_URL = "https://top.news.sina.com.cn/ws/GetTopDataList.php"
FINANCE_API_URL = "https://top.finance.sina.com.cn/ws/GetTopDataList.php"
CATEGORIES = (
    ("news", "新闻热榜", "www_www_all_suda_suda", SOURCE_URL, NEWS_API_URL),
    ("finance", "财经热榜", "finance_0_suda", "https://finance.sina.com.cn/", FINANCE_API_URL),
)


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


def _ranking_url(api_url: str, category: str) -> str:
    date = project_now().strftime("%Y%m%d")
    return (
        f"{api_url}?top_type=day&top_cat={category}&top_time={date}"
        "&top_show_num=20&top_order=DESC"
    )


def collect() -> "ChannelSnapshot":
    rankings = []
    for ranking_id, name, category, source_url, api_url in CATEGORIES:
        request_url = _ranking_url(api_url, category)
        items = parse_top_data(get(request_url, timeout=20, retries=2))
        rankings.append(Ranking(ranking_id, name, items, source_url, "新浪官方", request_url))
    return snapshot("sina", rankings)
