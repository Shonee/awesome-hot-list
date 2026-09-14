"""Fuliba latest article adapter using the public homepage."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://fuliba2023.net/"


def _number(text: str):
    match = re.search(r"([\d,]+)", text or "")
    return int(match.group(1).replace(",", "")) if match else None


def parse_articles(html: str) -> list[HotItem]:
    soup = BeautifulSoup(html or "", "html.parser")
    items = []
    seen = set()
    for article in soup.select("article.excerpt"):
        link = article.select_one("header h2 a[href]")
        if not link:
            continue
        title = link.get_text(" ", strip=True)
        url = urljoin(SOURCE_URL, link.get("href", ""))
        if not title or not url or url in seen:
            continue
        seen.add(url)

        category = article.select_one(".meta a.cat")
        note = article.select_one("p.note")
        views = article.select_one(".meta .views")
        comments = article.select_one(".meta a[href*='#comments']")
        published = article.select_one(".meta time")
        image = article.select_one("a.focus img[src]")
        comment_count = _number(comments.get_text(" ", strip=True)) if comments else None

        description_parts = []
        if category:
            category_parts = list(category.stripped_strings)
            if category_parts:
                description_parts.append(category_parts[-1])
        if comment_count is not None:
            description_parts.append(f"{comment_count} 条评论")
        if note:
            description_parts.append(note.get_text(" ", strip=True))

        items.append(
            HotItem(
                rank=len(items) + 1,
                title=title,
                url=url,
                hot=_number(views.get_text(" ", strip=True)) if views else comment_count,
                description=" · ".join(description_parts),
                image_url=urljoin(SOURCE_URL, image.get("src", "")) if image else "",
                published_at=published.get_text(" ", strip=True) if published else "",
            )
        )
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_articles(get(SOURCE_URL, timeout=15, retries=2))
    return snapshot(
        "fuliba",
        [
            Ranking(
                "latest",
                "最新文章",
                items,
                SOURCE_URL,
                provider_name="福利吧官方",
                provider_url=SOURCE_URL,
            )
        ],
    )
