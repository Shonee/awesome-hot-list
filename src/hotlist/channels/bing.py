"""Trending on Bing topics from the public Bing News page (US locale)."""

import logging
import subprocess
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.bing.com/news?cc=us&setlang=en-US"
logger = logging.getLogger(__name__)


def parse_trending(html: str | bytes) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select(".TrendingOnBing a[href*='/news/topicview']"):
        title = link.get_text(" ", strip=True)
        url = urljoin("https://www.bing.com/", link.get("href", ""))
        if not title or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 30:
            break
    return items


def collect() -> "ChannelSnapshot":
    try:
        items = parse_trending(get(SOURCE_URL, timeout=12, retries=1))
    except Exception as exc:  # noqa: BLE001 - try the alternate HTTP client on source challenges
        logger.warning("必应常规请求失败: %s", exc)
        items = []
    if not items:
        try:
            response = subprocess.run(
                ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "12", SOURCE_URL],
                capture_output=True,
                check=True,
                timeout=15,
            )
            items = parse_trending(response.stdout)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("必应备用请求失败: %s", exc)
    return snapshot("bing", [Ranking("trending-news", "Trending on Bing（美国新闻）", items, SOURCE_URL)])
