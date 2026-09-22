"""Small helpers shared by channel adapters."""

from datetime import datetime, timedelta
from html import unescape
from urllib.parse import urlparse
import warnings

from ..models import ChannelSnapshot, EmptySourceError, Ranking
from ..registry import get_channel
from src.utils.time_utils import PROJECT_TIMEZONE, now_string, project_now


def _published_datetime(value: str):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PROJECT_TIMEZONE)
    return parsed.astimezone(PROJECT_TIMEZONE)


def select_live_items(items, now=None, default_hours: int = 3, overflow_hours: int = 1, limit: int = 100):
    """Select a deterministic recent live-news window and renumber newest first."""
    now = (now or project_now()).astimezone(PROJECT_TIMEZONE)
    unique = {}
    for item in items:
        published = _published_datetime(item.published_at)
        if published is None or published > now:
            continue
        key = item.url or item.title
        previous = unique.get(key)
        if previous is None or published > previous[0]:
            unique[key] = (published, item)

    ordered = sorted(unique.values(), key=lambda pair: pair[0], reverse=True)
    selected = [pair for pair in ordered if pair[0] >= now - timedelta(hours=default_hours)]
    if len(selected) > limit:
        selected = [pair for pair in ordered if pair[0] >= now - timedelta(hours=overflow_hours)]
    selected = selected[:limit]
    for rank, (_published, item) in enumerate(selected, 1):
        item.rank = rank
    return [item for _published, item in selected]

def snapshot(channel_id: str, rankings: list[Ranking]) -> ChannelSnapshot:
    definition = get_channel(channel_id)
    if not any(ranking.items for ranking in rankings):
        raise EmptySourceError("source returned no usable items")
    return ChannelSnapshot(
        channel_id=channel_id,
        channel_name=definition.name,
        source_url=definition.homepage,
        fetched_at=now_string(),
        rankings=rankings,
    )


def unavailable(channel_id: str, reason: str) -> ChannelSnapshot:
    definition = get_channel(channel_id)
    return ChannelSnapshot.unavailable(
        channel_id=channel_id,
        channel_name=definition.name,
        source_url=definition.homepage,
        fetched_at=now_string(),
        status="disabled",
        error=reason,
    )


def clean_html(value) -> str:
    if not value:
        return ""
    from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MarkupResemblesLocatorWarning)
        return BeautifulSoup(unescape(str(value)), "html.parser").get_text(" ", strip=True)


def same_host(url: str, allowed_hosts) -> bool:
    """Validate an absolute URL against an explicit host allowlist."""
    return (urlparse(str(url or "")).hostname or "").lower() in {
        str(host).lower() for host in allowed_hosts
    }
