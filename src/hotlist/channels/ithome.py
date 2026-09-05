"""IT Home RSS adapter."""

from src.utils.http_utils import get

from ..models import Ranking
from .common import snapshot
from .rss import parse_feed


FEED_URL = "https://www.ithome.com/rss/"
SOURCE_URL = "https://www.ithome.com/"


def collect() -> "ChannelSnapshot":
    _, items = parse_feed(get(FEED_URL), FEED_URL)
    return snapshot("ithome", [Ranking("latest", "最新资讯", items, SOURCE_URL)])
