"""Readhub hot topics, daily briefing, and AI news adapter."""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import clean_html, snapshot


SOURCE_URL = "https://readhub.cn/"
PAGES = (
    ("hot", "24 小时热榜", "https://readhub.cn/hot"),
)
DAILY_URL = "https://readhub.cn/daily"
AI_URL = "https://readhub.cn/news/ai"
logger = logging.getLogger(__name__)


def parse_topic_links(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select("a[href^='/topic/']"):
        title = link.get_text(" ", strip=True)
        url = urljoin(SOURCE_URL, link.get("href", ""))
        if not title or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url))
        if len(items) >= 50:
            break
    return items


def parse_daily_links(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select("a[href^='/daily/']"):
        title = link.get_text(" ", strip=True)
        url = urljoin(SOURCE_URL, link.get("href", ""))
        published_at = link.get("href", "").rstrip("/").rsplit("/", 1)[-1]
        if not title or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url, published_at=published_at))
        if len(items) >= 30:
            break
    return items


def parse_ai_news(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for link in soup.select("a[target='_blank'][href^='http']"):
        title = link.get_text(" ", strip=True)
        url = link.get("href", "").strip()
        if not title or len(title) < 5 or url in seen or link.find_parent("footer"):
            continue
        container = link.find_parent("article") or link.parent
        text = clean_html(container.get_text(" ", strip=True) if container else "")
        description = text.replace(title, "", 1).strip()[:240]
        seen.add(url)
        items.append(HotItem(len(items) + 1, title, url, description=description))
        if len(items) >= 30:
            break
    return items


def collect() -> "ChannelSnapshot":
    rankings = []
    warnings = []
    for ranking_id, name, url in PAGES:
        try:
            items = parse_topic_links(get(url, timeout=20, retries=1))
        except Exception as exc:  # noqa: BLE001 - isolate each Readhub section
            logger.warning("Readhub %s 请求失败: %s", name, exc)
            items = []
            warnings.append(name)
        rankings.append(Ranking(ranking_id, name, items, url, "Readhub", url, "digest"))
    try:
        daily_items = parse_daily_links(get(DAILY_URL, timeout=20, retries=1))
    except Exception as exc:  # noqa: BLE001 - isolate each Readhub section
        logger.warning("Readhub 每日早报请求失败: %s", exc)
        daily_items = []
        warnings.append("每日早报")
    rankings.append(Ranking("daily", "每日早报", daily_items, DAILY_URL, "Readhub", DAILY_URL, "digest"))
    try:
        ai_items = parse_ai_news(get(AI_URL, timeout=20, retries=1))
    except Exception as exc:  # noqa: BLE001 - isolate each Readhub section
        logger.warning("Readhub AI 资讯请求失败: %s", exc)
        ai_items = []
        warnings.append("AI 资讯")
    rankings.append(Ranking("ai", "AI 资讯", ai_items, AI_URL, "Readhub", AI_URL, "digest"))
    result = snapshot("readhub", rankings)
    result.warnings = warnings
    return result
