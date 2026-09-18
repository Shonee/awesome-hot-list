"""CCTV News homepage adapter."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://news.cctv.com/"
ARTICLE_PATH = re.compile(r"/(?:20\d{2})/\d{2}/\d{2}/(?:ARTI|VIDE)[^/]+\.shtml$")


def parse_headlines(html: str | bytes) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select("a[href]"):
        title = link.get_text(" ", strip=True)
        url = urljoin(SOURCE_URL, link.get("href", ""))
        if not 6 <= len(title) <= 100 or not ARTICLE_PATH.search(url) or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_headlines(get(SOURCE_URL, res_type="bytes", timeout=20, retries=1))
    return snapshot("cctv", [Ranking("latest", "最新发布", items, SOURCE_URL, "央视网", SOURCE_URL, "authority")])
