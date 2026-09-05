"""Juejin hot article adapter."""

from urllib.parse import urlencode

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


API_URL = "https://api.juejin.cn/content_api/v1/content/article_rank"
SOURCE_URL = "https://juejin.cn/hot/articles"
REQUEST_PARAMS = {
    "category_id": "1",
    "type": "hot",
}


def _article_from_row(row: dict):
    content = row.get("content") or {}
    counter = row.get("content_counter") or {}
    if content.get("title"):
        created = content.get("ctime") or content.get("mtime")
        return HotItem(
            rank=1,
            title=content["title"],
            url=f"https://juejin.cn/post/{content.get('content_id')}" if content.get("content_id") else SOURCE_URL,
            hot=counter.get("hot_rank") or counter.get("view") or counter.get("like"),
            description=content.get("brief") or "",
            published_at=str(created) if created else "",
        )
    article = row.get("article_info") or row.get("articleInfo") or {}
    item = row.get("item_info") or row.get("itemInfo") or {}
    if not article and isinstance(item, dict):
        article = item.get("article_info") or item.get("articleInfo") or item
    title = article.get("title") or row.get("title")
    if not title:
        return None
    article_id = article.get("article_id") or article.get("articleId") or row.get("article_id") or row.get("articleId")
    url = article.get("article_url") or article.get("articleUrl")
    if not url and article_id:
        url = f"https://juejin.cn/post/{article_id}"
    if not url:
        url = SOURCE_URL
    return HotItem(
        rank=1,
        title=title,
        url=url,
        hot=article.get("view_count") or article.get("digg_count") or article.get("hot_rank"),
        description=article.get("brief_content") or article.get("briefContent") or "",
        image_url=article.get("cover_image") or article.get("coverImage") or "",
        published_at=str(article.get("ctime") or article.get("mtime") or ""),
    )


def parse_articles(payload: dict) -> list[HotItem]:
    """Normalize Juejin's nested recommendation response."""
    items = []
    seen = set()
    rows = (payload or {}).get("data") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidates = [row]
        item = row.get("item_info") or row.get("itemInfo")
        if isinstance(item, dict):
            candidates.insert(0, item)
        article = next((candidate for candidate in candidates if candidate.get("article_info") or candidate.get("articleInfo")), row)
        item = _article_from_row(article)
        if not item or item.title in seen:
            continue
        seen.add(item.title)
        item.rank = len(items) + 1
        items.append(item)
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    query = urlencode(REQUEST_PARAMS)
    payload = get(
        f"{API_URL}?{query}",
        res_type="json",
        headers={"Referer": "https://juejin.cn/"},
    )
    return snapshot("juejin", [Ranking("hot", "热门文章", parse_articles(payload), SOURCE_URL)])
