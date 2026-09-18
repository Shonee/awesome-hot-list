"""Ministry of Foreign Affairs press-conference adapter."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.mfa.gov.cn/web/wjdt_674879/fyrbt_674889/"
DATE_PATTERN = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def parse_briefings(html: str | bytes) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select(".newsBd li a[href]"):
        title = link.get_text(" ", strip=True)
        url = urljoin(SOURCE_URL, link.get("href", ""))
        if not title or url in seen:
            continue
        match = DATE_PATTERN.search(title)
        published_at = match.group(0) if match else ""
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url, published_at=published_at))
        if len(items) >= 30:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_briefings(get(SOURCE_URL, res_type="bytes", timeout=20, retries=1))
    return snapshot("mfa", [Ranking("briefings", "例行记者会", items, SOURCE_URL, "外交部", SOURCE_URL, "authority")])
