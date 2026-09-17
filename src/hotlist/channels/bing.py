"""Domestic trending topics from the public Chinese Bing homepage."""

import logging
import subprocess
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot, unavailable


SOURCE_URL = "https://www.bing.com/?mkt=zh-CN&cc=cn&setlang=zh-hans"
logger = logging.getLogger(__name__)


def _is_domestic_title(title: str) -> bool:
    han = len(re.findall(r"[\u4e00-\u9fff]", title))
    kana = len(re.findall(r"[\u3040-\u30ff]", title))
    return han >= 2 and kana <= max(1, han // 5)


def parse_domestic_trending(html: str | bytes) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for title_node in soup.select("#tobPrompt .tob_title, .tob_title"):
        title = title_node.get_text(" ", strip=True)
        link = title_node if title_node.name == "a" else title_node.find_parent("a")
        href = link.get("href", "") if link else ""
        url = urljoin("https://www.bing.com/", href) if href else f"https://www.bing.com/search?q={quote_plus(title)}"
        if not _is_domestic_title(title) or title in seen:
            continue
        seen.add(title)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 30:
            break
    return items


def parse_trending(html: str | bytes) -> list[HotItem]:
    """Compatibility alias retained for callers of the previous parser."""
    return parse_domestic_trending(html)


def collect() -> "ChannelSnapshot":
    try:
        items = parse_domestic_trending(
            get(
                SOURCE_URL,
                headers={"Accept-Language": "zh-CN,zh;q=0.9"},
                timeout=12,
                retries=1,
            )
        )
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
            items = parse_domestic_trending(response.stdout)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("必应备用请求失败: %s", exc)
    if len(items) < 3:
        return unavailable("bing", f"Bing 国内热点仅返回 {len(items)} 条有效数据")
    return snapshot("bing", [Ranking("domestic-trending", "国内热点", items, SOURCE_URL, "必应官方", SOURCE_URL)])
