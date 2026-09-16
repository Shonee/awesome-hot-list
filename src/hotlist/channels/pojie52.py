"""吾爱破解 hot thread adapter."""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.52pojie.cn/forum.php?mod=guide&view=hot"
DIGEST_URL = "https://www.52pojie.cn/forum.php?mod=guide&view=digest"
logger = logging.getLogger(__name__)


def _number(value: str):
    match = re.search(r"(\d[\d,]*)", value or "")
    return int(match.group(1).replace(",", "")) if match else None


def parse_hot_threads(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = ("a.xst[href]", "th.common a[href*='thread']", "a[href*='thread-']")
    links = []
    for selector in selectors:
        links.extend(soup.select(selector))
    items = []
    seen = set()
    for link in links:
        title = link.get_text(" ", strip=True)
        url = urljoin("https://www.52pojie.cn/", link.get("href", ""))
        if not title or "thread" not in url or url in seen:
            continue
        seen.add(url)
        context = link.parent.parent.get_text(" ", strip=True) if link.parent and link.parent.parent else ""
        items.append(HotItem(len(items) + 1, title, url, hot=_number(context)))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_hot_threads(get(SOURCE_URL))
    rankings = [Ranking("hot", "人气热门", items, SOURCE_URL)]
    warnings = []
    try:
        digest = parse_hot_threads(get(DIGEST_URL, timeout=12, retries=1))
        if digest:
            rankings.append(Ranking("digest", "精华采撷", digest, DIGEST_URL))
        else:
            warnings.append("精华采撷")
    except Exception as exc:  # noqa: BLE001 - optional ranking cannot break hot posts
        logger.warning("吾爱精华采撷请求失败: %s", exc)
        warnings.append("精华采撷")
    result = snapshot("pojie52", rankings)
    result.warnings = warnings
    return result
