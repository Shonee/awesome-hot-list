"""Cailian Press hot-news adapter using the homepage SSR payload."""

import json
import logging
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from src.utils.http_utils import get
from src.utils.time_utils import project_now, timestamp_string

from ..models import HotItem, Ranking
from .common import clean_html, select_live_items, snapshot


SOURCE_URL = "https://www.cls.cn/telegraph"
DETAIL_URL = "https://www.cls.cn/detail/{}"
LIVE_API_URL = "https://www.cls.cn/api/cache"
logger = logging.getLogger(__name__)


def _published_at(timestamp) -> str:
    return timestamp_string(timestamp)


def _next_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("script#__NEXT_DATA__")
    if not script:
        return {}
    try:
        return json.loads(script.get_text())
    except json.JSONDecodeError:
        return {}


def parse_hot_articles(html: str) -> list[HotItem]:
    """Read the current homepage's serialized hot-article list."""
    payload = _next_data(html)
    rows = payload.get("props", {}).get("pageProps", {}).get("hotArticleData", [])
    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        article_id = row.get("id")
        if not title or not article_id or title in seen:
            continue
        seen.add(title)
        items.append(
            HotItem(
                rank=len(items) + 1,
                title=title,
                url=DETAIL_URL.format(article_id),
                hot=row.get("readNum"),
                description=str(row.get("brief") or "").strip(),
                image_url=str(row.get("img") or "").strip(),
                published_at=_published_at(row.get("ctime")),
            )
        )
        if len(items) >= 50:
            break
    return items


def parse_live_payload(payload: dict) -> list[HotItem]:
    rows = payload.get("data", {}).get("roll_data", []) if isinstance(payload, dict) and payload.get("errno") == 0 else []
    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        article_id = row.get("id")
        title = clean_html(row.get("title") or row.get("brief") or row.get("content"))
        if not article_id or not title or article_id in seen:
            continue
        seen.add(article_id)
        items.append(
            HotItem(
                len(items) + 1,
                title,
                DETAIL_URL.format(article_id),
                hot=row.get("reading_num"),
                description=clean_html(row.get("brief")),
                published_at=_published_at(row.get("ctime")),
            )
        )
    return items


def collect_live() -> "ChannelSnapshot":
    query = urlencode({"rn": 200, "lastTime": int(project_now().timestamp()), "name": "telegraph"})
    request_url = f"{LIVE_API_URL}?{query}"
    live_items = select_live_items(parse_live_payload(get(request_url, res_type="json", timeout=20, retries=1)))
    return snapshot(
        "cls",
        [Ranking("live", "电报", live_items, SOURCE_URL, "财联社官方", request_url, "live")],
    )


def collect() -> "ChannelSnapshot":
    html = get("https://www.cls.cn/")
    rankings = [Ranking("hot", "热门文章", parse_hot_articles(html), "https://www.cls.cn/")]
    warnings = []
    try:
        live_ranking = collect_live().rankings[0]
    except Exception as exc:  # noqa: BLE001 - keep the homepage ranking on live-source failure
        logger.warning("财联社电报请求失败: %s", exc)
        live_ranking = Ranking("live", "电报", [], SOURCE_URL, "财联社官方", LIVE_API_URL, "live")
        warnings.append("电报")
    rankings.append(live_ranking)
    result = snapshot("cls", rankings)
    result.warnings = warnings
    return result
