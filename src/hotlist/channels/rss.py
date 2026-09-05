"""RSS and Atom feed adapters."""

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import clean_html, snapshot, unavailable

logger = logging.getLogger(__name__)
RSS_LIMIT = 5
DEFAULT_FEEDS = (
    ("少数派", "https://sspai.com/feed"),
    ("爱范儿", "https://www.ifanr.com/feed"),
    ("量子位", "https://www.qbitai.com/feed"),
    ("InfoQ", "https://www.infoq.cn/feed"),
    ("极客公园", "https://www.geekpark.net/rss"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
    ("Hacker News", "https://hnrss.org/frontpage"),
    ("AI News", "https://www.artificialintelligence-news.com/feed/"),
    ("阮一峰网络日志", "https://www.ruanyifeng.com/blog/atom.xml"),
)


def _published_key(value: str) -> float:
    if not value:
        return float("-inf")
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return float("-inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _limit_items(items: list[HotItem], limit: int = RSS_LIMIT) -> list[HotItem]:
    limited = sorted(items, key=lambda item: _published_key(item.published_at), reverse=True)[:limit]
    for rank, item in enumerate(limited, 1):
        item.rank = rank
    return limited


def parse_feed(xml_text: str, source_url: str = "", limit: int = RSS_LIMIT) -> tuple[str, list[HotItem]]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is not None:
        name = (channel.findtext("title") or source_url or "RSS").strip()
        items = []
        for index, row in enumerate(channel.findall("item"), 1):
            title = (row.findtext("title") or "").strip()
            if title:
                items.append(HotItem(index, title, (row.findtext("link") or "").strip(), description=clean_html(row.findtext("description")), published_at=(row.findtext("pubDate") or "").strip()))
        return name, _limit_items(items, limit)

    namespace = "{http://www.w3.org/2005/Atom}"
    name = (root.findtext(f"{namespace}title") or source_url or "RSS").strip()
    items = []
    for index, row in enumerate(root.findall(f"{namespace}entry"), 1):
        title = (row.findtext(f"{namespace}title") or "").strip()
        link_node = row.find(f"{namespace}link")
        link = link_node.get("href", "") if link_node is not None else ""
        if title:
            items.append(HotItem(index, title, link, description=clean_html(row.findtext(f"{namespace}summary") or row.findtext(f"{namespace}content")), published_at=(row.findtext(f"{namespace}updated") or "").strip()))
    return name, _limit_items(items, limit)


def _feed_id(name: str, index: int) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or f"feed-{index}"


def collect() -> "ChannelSnapshot":
    raw = os.environ.get("HOTLIST_RSS_FEEDS", "").strip()
    feeds = []
    if raw:
        for feed in [part.strip() for part in re.split(r"[\n,]", raw) if part.strip()]:
            configured_name, separator, url = feed.partition("|")
            feeds.append((configured_name.strip() if separator else "", url.strip() if separator else configured_name.strip()))
    else:
        feeds = list(DEFAULT_FEEDS)

    try:
        limit = max(1, min(RSS_LIMIT, int(os.environ.get("HOTLIST_RSS_LIMIT", RSS_LIMIT))))
    except ValueError:
        limit = RSS_LIMIT

    rankings = []
    for index, (configured_name, feed_url) in enumerate(feeds, 1):
        try:
            name, items = parse_feed(get(feed_url), feed_url, limit=limit)
        except Exception as exc:  # noqa: BLE001 - one feed must not hide other feeds
            logger.warning("RSS 请求失败: %s: %s", feed_url, exc)
            continue
        name = configured_name.strip() or name
        if items:
            rankings.append(Ranking(_feed_id(name, index), name, items, feed_url))
    if not rankings:
        return unavailable("rss", "no RSS feed returned usable items")
    return snapshot("rss", rankings)
