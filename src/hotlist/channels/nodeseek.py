"""NodeSeek hot topic adapter using public HTML or serialized page data."""

import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://www.nodeseek.com/?tab=hot"
RELATIVE_TIME = re.compile(
    r"^\d+\s*(?:s|m|min|h|d|w|mo|y)(?:\s+\d+\s*(?:s|m|min|h|d))?\s+ago$",
    re.I,
)


def _is_topic_link(href: str, title: str) -> bool:
    if not href or RELATIVE_TIME.fullmatch(title.strip()):
        return False
    parsed = urlsplit(href)
    if parsed.fragment:
        return False
    return bool(
        re.fullmatch(r"/thread/\d+/?", parsed.path)
        or re.fullmatch(r"/post-\d+-1(?:\.html)?/?", parsed.path)
    )


def _json_rows(soup: BeautifulSoup) -> list[dict]:
    rows = []
    for script in soup.select("script[type='application/json']"):
        try:
            value = json.loads(script.get_text())
        except (TypeError, ValueError):
            continue
        candidates = value if isinstance(value, list) else value.get("data", []) if isinstance(value, dict) else []
        if isinstance(candidates, list):
            rows.extend(row for row in candidates if isinstance(row, dict) and row.get("title"))
    return rows


def parse_topics(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for row in _json_rows(soup):
        title = str(row.get("title") or "").strip()
        url = row.get("url") or row.get("link") or ""
        if title and url:
            items.append(HotItem(len(items) + 1, title, urljoin(SOURCE_URL, str(url)), hot=row.get("replies") or row.get("views")))
    if items:
        return items[:50]

    selectors = ("a.topic-title[href]", "a.post-title[href]", "a[href*='/thread/']", "a[href*='/post-']")
    for link in [link for selector in selectors for link in soup.select(selector)]:
        title = link.get_text(" ", strip=True)
        href = link.get("href", "")
        url = urljoin(SOURCE_URL, href)
        if not title or not _is_topic_link(href, title) or url in seen:
            continue
        seen.add(url)
        context = link.parent.get_text(" ", strip=True) if link.parent else ""
        metric = re.search(r"(\d+)\s*(?:回复|浏览|views?|repl(?:y|ies))", context, re.I)
        items.append(HotItem(len(items) + 1, title, url, hot=int(metric.group(1)) if metric else None))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    return snapshot("nodeseek", [Ranking("hot", "热门主题", parse_topics(get(SOURCE_URL, timeout=12, retries=1)), SOURCE_URL)])
