"""Small helpers shared by channel adapters."""

import time
from html import unescape

from bs4 import BeautifulSoup

from ..models import ChannelSnapshot, Ranking
from ..registry import get_channel


def now_string() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def snapshot(channel_id: str, rankings: list[Ranking]) -> ChannelSnapshot:
    definition = get_channel(channel_id)
    if not any(ranking.items for ranking in rankings):
        raise RuntimeError("source returned no usable items")
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
    return BeautifulSoup(unescape(str(value)), "html.parser").get_text(" ", strip=True)
