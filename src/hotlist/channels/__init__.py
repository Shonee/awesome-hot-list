"""Channel adapter registry.

Each module in this package owns one source's request and parsing rules. The
public collector contract is a ``ChannelSnapshot``; persistence stays in the
CLI and runner layers.
"""

from typing import Callable

from ..models import ChannelSnapshot
from . import acfun, bilibili, cls, cnblogs, douban, douyin, github, hupu, ithome, juejin, kr36, linuxdo, maimai, nodeseek, pojie52, qqnews, rss, stackoverflow, tieba, tonghuashun, toutiao, v2ex, weibo, xueqiu, zhihu
from .acfun import parse_rank as parse_acfun
from .bilibili import parse_hot_search as parse_bilibili_hot_search
from .bilibili import parse_videos as parse_bilibili_videos
from .cnblogs import parse_rank as parse_cnblogs
from .douban import parse_topics as parse_douban
from .douyin import extract_cover_url
from .github import parse_trending
from .hupu import parse_topics as parse_hupu
from .juejin import parse_articles as parse_juejin
from .linuxdo import parse_topics as parse_linuxdo
from .kr36 import parse_hot as parse_36kr
from .nodeseek import parse_topics as parse_nodeseek
from .pojie52 import parse_hot_threads as parse_pojie52
from .qqnews import parse_news as parse_qqnews
from .rss import parse_feed as parse_rss
from .cls import parse_hot_articles as parse_cls_hot_articles
from .stackoverflow import parse_questions
from .tieba import parse_topics as parse_tieba
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
    "cnblogs": cnblogs.collect,
    "linuxdo": linuxdo.collect,
    "nodeseek": nodeseek.collect,
    "pojie52": pojie52.collect,
    "qqnews": qqnews.collect,
    "tieba": tieba.collect,
}


def collect_channel(channel_id: str) -> ChannelSnapshot:
    try:
        collector = COLLECTORS[channel_id]
    except KeyError as exc:
        raise ValueError(f"collector is not registered: {channel_id}") from exc
    return collector()


__all__ = ["COLLECTORS", "collect_channel", "parse_36kr", "parse_acfun", "parse_bilibili_hot_search", "parse_bilibili_videos", "parse_cnblogs", "parse_cls_hot_articles", "parse_douban", "parse_hupu", "parse_juejin", "parse_linuxdo", "parse_nodeseek", "parse_pojie52", "parse_qqnews", "parse_rss", "parse_questions", "parse_tieba", "parse_v2ex", "parse_toutiao", "parse_weibo", "parse_xueqiu", "parse_trending", "extract_cover_url"]
