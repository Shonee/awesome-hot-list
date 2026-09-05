"""GitHub Trending adapter with a small Search API fallback."""

import datetime
import logging
import re
import time
from enum import Enum

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


GITHUB_HOST = "https://github.com"
TRENDING_URL = "https://github.com/trending/{}?since={}"
SEARCH_API = "https://api.github.com/search/repositories"
SEARCH_WINDOW_DAYS = {"daily": 7, "weekly": 30, "monthly": 90}
SEARCH_API_INTERVAL = 7
logger = logging.getLogger(__name__)


class Since(Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class Language(Enum):
    all = ""
    java = "java"
    python = "python"
    go = "go"
    html = "html"
    javascript = "javascript"


def _text(node) -> str:
    return node.get_text(strip=True) if node else ""


def _find_by_href(node, suffix: str):
    return node.find("a", href=lambda value: value and value.rstrip("/").endswith(suffix))


def _stars_today(article) -> str:
    span = article.find("span", class_="d-inline-block float-sm-right")
    text = _text(span)
    match = re.search(r"([\d,]+\s+stars\s+today)", article.get_text(" ", strip=True))
    return text or (match.group(1) if match else "")


def parse_trending(html: str, language: str = "", since: str = "daily") -> list[HotItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for index, article in enumerate(soup.find_all("article", class_="Box-row"), 1):
        heading = article.find("h2")
        link = heading.find("a", href=True) if heading else None
        if not link:
            continue
        parts = link["href"].strip("/").split("/")
        if len(parts) < 2:
            continue
        owner, repo = parts[:2]
        language_text = _text(article.find("span", itemprop="programmingLanguage"))
        stars_today = _stars_today(article)
        description = _text(article.find("p"))
        if language_text or stars_today:
            description = " · ".join(part for part in (description, language_text, stars_today) if part)
        items.append(HotItem(index, repo, f"{GITHUB_HOST}/{owner}/{repo}", hot=_text(_find_by_href(article, "/stargazers")), description=description))
    return items


def fetch_trending(language: str = "", since: str = "daily") -> list[HotItem]:
    html = get(TRENDING_URL.format(language, since))
    return parse_trending(html, language, since)


def fetch_via_search_api(since: str = "daily", per_page: int = 25) -> list[HotItem]:
    days = SEARCH_WINDOW_DAYS.get(since, 7)
    since_date = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    url = f"{SEARCH_API}?q=created:>{since_date}&sort=stars&order=desc&per_page={per_page}"
    payload = get(url, res_type="json")
    items = []
    for index, row in enumerate((payload or {}).get("items", []), 1):
        full_name = row.get("full_name", "")
        owner = (row.get("owner") or {}).get("login", "")
        repo = row.get("name") or full_name.split("/")[-1]
        items.append(
            HotItem(
                index,
                repo,
                row.get("html_url") or f"{GITHUB_HOST}/{full_name}",
                hot=row.get("stargazers_count"),
                description=row.get("description") or "",
            )
        )
    return items


def _collect_rankings() -> dict[str, list[HotItem]]:
    rankings = {}
    for since in Since:
        try:
            rankings[since.value] = fetch_trending("", since.value)
        except Exception as exc:  # noqa: BLE001 - one ranking must not abort the channel
            logger.warning("GitHub Trending 请求失败: since=%s: %s", since.value, exc)
            rankings[since.value] = []
        time.sleep(0.1)

    for language in Language:
        if language is Language.all:
            continue
        try:
            rankings[language.value] = fetch_trending(language.value, Since.weekly.value)
        except Exception as exc:  # noqa: BLE001 - one language must not abort the channel
            logger.warning("GitHub Trending 请求失败: language=%s: %s", language.value, exc)
            rankings[language.value] = []
        time.sleep(0.1)

    if not any(rankings.values()):
        logger.warning("GitHub Trending 全部为空，启用 Search API 兜底")
        rankings = {}
        for since in Since:
            try:
                rankings[since.value] = fetch_via_search_api(since.value)
            except Exception as exc:  # noqa: BLE001 - keep other fallback periods
                logger.error("GitHub Search API 兜底失败: since=%s: %s", since.value, exc)
                rankings[since.value] = []
            time.sleep(SEARCH_API_INTERVAL)
    return rankings


def collect() -> "ChannelSnapshot":
    names = {
        "daily": "每日趋势",
        "weekly": "每周趋势",
        "monthly": "每月趋势",
        "java": "Java",
        "python": "Python",
        "go": "Go",
        "html": "HTML",
        "javascript": "JavaScript",
    }
    rankings = []
    for ranking_id, items in _collect_rankings().items():
        language = "" if ranking_id in {"daily", "weekly", "monthly"} else ranking_id
        since = ranking_id if ranking_id in {"daily", "weekly", "monthly"} else "weekly"
        source_url = TRENDING_URL.format(language, since)
        rankings.append(Ranking(ranking_id, names.get(ranking_id, ranking_id), items, source_url))
    return snapshot("github", rankings)
