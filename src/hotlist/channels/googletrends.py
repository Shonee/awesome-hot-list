"""Google Trends official Trending Now page adapter."""

import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


GEO = "HK"
SOURCE_URL = f"https://trends.google.com/trending?geo={GEO}"


def _data_block(html: str):
    marker = "AF_initDataCallback({key: 'ds:0'"
    start = (html or "").find(marker)
    if start < 0:
        return None
    data_start = html.find("data:", start)
    if data_start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(html[data_start + len("data:"):])
    except json.JSONDecodeError:
        return None
    return data


def parse_trending_page(html: str) -> list[HotItem]:
    data = _data_block(html)
    rows = data[1] if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list) else []
    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        title = str(row[0] or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        geo = str(row[2] or GEO) if len(row) > 2 else GEO
        timestamps = row[3] if len(row) > 3 and isinstance(row[3], list) else []
        published = ""
        if timestamps and isinstance(timestamps[0], (int, float)):
            published = datetime.fromtimestamp(timestamps[0], timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        hot = row[6] if len(row) > 6 else None
        related = row[9] if len(row) > 9 and isinstance(row[9], list) else []
        query = urlencode({"q": title, "geo": geo})
        items.append(
            HotItem(
                len(items) + 1,
                title,
                f"https://trends.google.com/trends/explore?{query}",
                hot=hot,
                description="相关：" + "、".join(map(str, related[:3])) if related else "",
                published_at=published,
            )
        )
        if len(items) >= 20:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_trending_page(get(SOURCE_URL, timeout=30, retries=2))
    return snapshot(
        "googletrends",
        [Ranking("hk", "香港趋势", items, SOURCE_URL, "Google Trends 官方", SOURCE_URL)],
    )
