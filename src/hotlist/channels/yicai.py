"""Yicai editorial homepage headlines and official 7x24 briefs."""

import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import clean_html, same_host, select_live_items, snapshot


SOURCE_URL = "https://www.yicai.com/"
LIVE_SOURCE_URL = "https://www.yicai.com/brief/"
LIVE_API_URL = "https://www.yicai.com/api/ajax/getbrieflist?page=1&pagesize=20&type=0&id=all&action=mix"
logger = logging.getLogger(__name__)


def parse_headlines(html: str | bytes) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select(".swiper-wrapper .swiper-slide.item a[href]"):
        url = urljoin(SOURCE_URL, link.get("href", ""))
        title_node = link.select_one("h2")
        title = title_node.get_text(" ", strip=True) if title_node else link.get_text(" ", strip=True)
        if not title or not same_host(url, {"www.yicai.com"}) or "/news/" not in urlparse(url).path or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 20:
            break
    return items


def parse_live_payload(payload: list) -> list[HotItem]:
    items = []
    seen = set()
    for row in payload if isinstance(payload, list) else []:
        if not isinstance(row, dict):
            continue
        title = clean_html(row.get("LiveTitle"))
        published = str(row.get("CreateDate") or "").strip()
        url = str(row.get("ShareUrl") or "").strip()
        host = (urlparse(url).hostname or "").lower()
        if not title or not published or not same_host(url, {"www.yicai.com", "m.yicai.com"}) or "/brief/" not in urlparse(url).path or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url, published_at=published))
    items.sort(key=lambda item: item.published_at, reverse=True)
    for index, item in enumerate(items, 1):
        item.rank = index
    return items


def collect_live() -> "ChannelSnapshot":
    payload = get(LIVE_API_URL, res_type="json", headers={"Referer": LIVE_SOURCE_URL}, timeout=20, retries=1)
    items = select_live_items(parse_live_payload(payload))
    return snapshot("yicai", [Ranking("live", "7x24", items, LIVE_SOURCE_URL, "第一财经官方", LIVE_API_URL, "live")])


def collect() -> "ChannelSnapshot":
    items = parse_headlines(get(SOURCE_URL, res_type="bytes", timeout=20, retries=1))
    return snapshot("yicai", [Ranking("headlines", "首页头条", items, SOURCE_URL, "第一财经官方", SOURCE_URL)])
