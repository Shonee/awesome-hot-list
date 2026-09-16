"""Cnblogs homepage, editor picks and 48-hour reading ranking."""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.cnblogs.com/"
PICKS_URL = "https://www.cnblogs.com/pick/"
READING_URL = "https://www.cnblogs.com/aggsite/SideRight"
logger = logging.getLogger(__name__)


def _recommend_count(value: str):
    match = re.search(r"推荐\s*(\d+)", value or "")
    return int(match.group(1)) if match else None


def parse_rank(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("#post_list")
    links = (body or soup).select(".post-item a.post-item-title[href]")
    if not body and not links:
        links = soup.select("a.post-item-title[href]")
    items = []
    seen = set()
    for link in links:
        title = link.get_text(" ", strip=True)
        url = urljoin("https://www.cnblogs.com/", link.get("href", ""))
        if not title or "/p/" not in url or url in seen:
            continue
        seen.add(url)
        parent = link.parent.parent if link.parent else link
        context = parent.get_text(" ", strip=True) if parent else ""
        items.append(HotItem(len(items) + 1, title, url, hot=_recommend_count(context)))
        if len(items) >= 50:
            break
    return items


def parse_reading_rank(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    card = next(
        (card for card in soup.select(".card")
         if "48小时阅读排行" in (card.select_one(".card-title") or card).get_text(" ", strip=True)),
        None,
    )
    if not card:
        return []
    items = []
    seen = set()
    for link in card.select("a[href*='/p/']"):
        title = link.get_text(" ", strip=True)
        url = urljoin(SOURCE_URL, link.get("href", ""))
        if title and url not in seen:
            seen.add(url)
            items.append(HotItem(len(items) + 1, title, url))
    return items[:50]


def collect() -> "ChannelSnapshot":
    rankings = []
    warnings = []
    for ranking_id, name, url, parser in (
        ("latest", "最新帖子", SOURCE_URL, parse_rank),
        ("picks", "精华帖子", PICKS_URL, parse_rank),
        ("reading-48h", "48 小时阅读排行", READING_URL, parse_reading_rank),
    ):
        try:
            items = parser(get(url, timeout=12, retries=1))
            if not items:
                raise ValueError("no article links in source")
            rankings.append(Ranking(ranking_id, name, items, url))
        except Exception as exc:  # noqa: BLE001 - keep independent lists available
            logger.warning("博客园 %s 获取失败: %s", name, exc)
            warnings.append(name)
    result = snapshot("cnblogs", rankings)
    result.warnings = warnings
    return result
