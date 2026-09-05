"""Channel adapter registry.

Each module in this package owns one source's request and parsing rules. The
public collector contract is a ``ChannelSnapshot``; persistence stays in the
CLI and runner layers.
"""

from typing import Callable

from ..models import ChannelSnapshot
from . import acfun, bilibili, cls, douban, douyin, github, hupu, ithome, juejin, kr36, maimai, rss, stackoverflow, tonghuashun, toutiao, v2ex, weibo, xueqiu, zhihu
from .acfun import parse_rank as parse_acfun
from .bilibili import parse_hot_search as parse_bilibili_hot_search
from .bilibili import parse_videos as parse_bilibili_videos
from .douban import parse_topics as parse_douban
from .douyin import extract_cover_url
from .github import parse_trending
from .hupu import parse_topics as parse_hupu
from .juejin import parse_articles as parse_juejin
from .kr36 import parse_hot as parse_36kr
from .rss import parse_feed as parse_rss
from .cls import parse_hot_articles as parse_cls_hot_articles
from .stackoverflow import parse_questions
from .toutiao import parse_hot as parse_toutiao
from .v2ex import parse_topics as parse_v2ex
from .weibo import parse_hot as parse_weibo
from .xueqiu import parse_topics as parse_xueqiu


COLLECTORS: dict[str, Callable[[], ChannelSnapshot]] = {
    "bilibili": bilibili.collect,
    "douyin": douyin.collect,
    "weibo": weibo.collect,
    "zhihu": zhihu.collect,
    "github": github.collect,
    "toutiao": toutiao.collect,
    "rss": rss.collect,
    "acfun": acfun.collect,
    "ithome": ithome.collect,
    "douban": douban.collect,
    "hupu": hupu.collect,
    "juejin": juejin.collect,
    "v2ex": v2ex.collect,
    "stackoverflow": stackoverflow.collect,
    "cls": cls.collect,
    "36kr": kr36.collect,
    "tonghuashun": tonghuashun.collect,
    "maimai": maimai.collect,
    "xueqiu": xueqiu.collect,
}


def collect_channel(channel_id: str) -> ChannelSnapshot:
    try:
        collector = COLLECTORS[channel_id]
    except KeyError as exc:
        raise ValueError(f"collector is not registered: {channel_id}") from exc
    return collector()


__all__ = ["COLLECTORS", "collect_channel", "parse_36kr", "parse_acfun", "parse_bilibili_hot_search", "parse_bilibili_videos", "parse_cls_hot_articles", "parse_douban", "parse_hupu", "parse_juejin", "parse_rss", "parse_questions", "parse_v2ex", "parse_toutiao", "parse_weibo", "parse_xueqiu", "parse_trending", "extract_cover_url"]
