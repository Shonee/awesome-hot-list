"""Channel metadata and lazy collector registry."""

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Tuple

from .models import ChannelSnapshot


Collector = Callable[[], ChannelSnapshot]


@dataclass(frozen=True)
class ChannelDefinition:
    channel_id: str
    name: str
    order: int
    short_name: str
    color: str
    collector: Optional[Collector]
    homepage: str = ""
    enabled_by_default: bool = True
    requires_env: Tuple[str, ...] = ()
    frequency_minutes: int = 60
    visible_by_default: bool = True
    include_in_report: bool = True


CHANNEL_ORDER = (
    "bilibili",
    "douyin",
    "kuaishou",
    "weibo",
    "zhihu",
    "baidu",
    "github",
    "hackernews",
    "huggingface",
    "googletrends",
    "juejin",
    "lobsters",
    "toutiao",
    "qqnews",
    "netease",
    "sina",
    "thepaper",
    "acfun",
    "douban",
    "hupu",
    "36kr",
    "tonghuashun",
    "eastmoney",
    "maimai",
    "xueqiu",
    "v2ex",
    "stackoverflow",
    "cls",
    "cnblogs",
    "nodeseek",
    "pojie52",
    "wechat",
    "tieba",
    "fuliba",
    "rss",
)

RETIRED_CHANNEL_IDS = ("linuxdo", "ithome")

# GitHub Actions checks special channels hourly, but the collector only runs a
# channel when this interval has elapsed since its last snapshot. This keeps
# one scheduling model while allowing less stable or slower sources to opt out
# of a full hourly request.
CHANNEL_FREQUENCIES = {
    "github": 360,
    "googletrends": 360,
    "huggingface": 360,
    "kuaishou": 180,
    "eastmoney": 180,
    "hackernews": 120,
    "xueqiu": 360,
    "maimai": 360,
    "v2ex": 180,
}


def _lazy(channel_id: str) -> Collector:
    def collect() -> ChannelSnapshot:
        from .channels import collect_channel

        return collect_channel(channel_id)

    return collect


_METADATA = {
    "weibo": ("微博", "WB", "#e6162d", "https://s.weibo.com/top/summary", True, ()),
    "douyin": ("抖音", "DY", "#161823", "https://www.douyin.com/hot", True, ()),
    "kuaishou": ("快手", "KS", "#ff5000", "https://www.kuaishou.com/?isHome=1&cc=CN", True, ()),
    "zhihu": ("知乎", "ZH", "#1772f6", "https://www.zhihu.com/hot", True, ()),
    "baidu": ("百度热搜", "百", "#315efb", "https://top.baidu.com/board?tab=realtime", True, ()),
    "bilibili": ("哔哩哔哩", "BILI", "#fb7299", "https://www.bilibili.com/v/popular/all", True, ()),
    "toutiao": ("今日头条", "TT", "#f04142", "https://www.toutiao.com/hot-event/hot-board/", True, ()),
    "cls": ("财联社", "财", "#c72b2b", "https://www.cls.cn/telegraph", True, ()),
    "36kr": ("36氪", "36", "#0066ff", "https://www.36kr.com/hot-list/catalog", True, ()),
    "pojie52": ("吾爱破解", "吾", "#c44c42", "https://www.52pojie.cn/forum.php?mod=guide&view=hot", True, ()),
    "acfun": ("AcFun", "AC", "#fd4c5d", "https://www.acfun.cn/rank/list/", True, ()),
    "tonghuashun": ("同花顺", "THS", "#e83b35", "https://t.10jqka.com.cn/", True, ()),
    "eastmoney": ("东方财富", "东", "#f04444", "https://guba.eastmoney.com/rank/", True, ()),
    "github": ("GitHub", "GH", "#24292f", "https://github.com/trending", True, ()),
    "hackernews": ("Hacker News", "HN", "#ff6600", "https://news.ycombinator.com/", True, ()),
    "huggingface": ("Hugging Face", "HF", "#e0a000", "https://huggingface.co/models?sort=trending", True, ()),
    "googletrends": ("Google Trends", "G", "#4285f4", "https://trends.google.com/trending?geo=HK", True, ()),
    "juejin": ("掘金", "掘", "#1e80ff", "https://juejin.cn/hot/articles", True, ()),
    "lobsters": ("Lobsters", "L", "#ac130d", "https://lobste.rs/", True, ()),
    "douban": ("豆瓣", "DB", "#00a65a", "https://movie.douban.com/chart", True, ()),
    "hupu": ("虎扑", "HP", "#b31b1b", "https://bbs.hupu.com/all-gambia", True, ()),
    "qqnews": ("腾讯新闻", "腾", "#1769aa", "https://news.qq.com/", True, ()),
    "netease": ("网易新闻", "网", "#d22128", "https://news.163.com/", True, ()),
    "sina": ("新浪", "新", "#e6162d", "https://news.sina.com.cn/", True, ()),
    "thepaper": ("澎湃新闻", "澎", "#b5121b", "https://www.thepaper.cn/", True, ()),
    "wechat": ("微信文章", "微", "#07c160", "https://tophub.today/n/WnBe01o371", True, ()),
    "maimai": ("脉脉", "MM", "#00a6a6", "https://maimai.cn/web/gossip_list", False, ("MAIMAI_COOKIE",)),
    "xueqiu": ("雪球", "XQ", "#1f6fb2", "https://xueqiu.com/today", True, ()),
    "v2ex": ("V2EX", "V2", "#778087", "https://www.v2ex.com/?tab=hot", True, ()),
    "stackoverflow": ("Stack Overflow", "SO", "#f48024", "https://stackoverflow.com/questions?tab=hot", True, ()),
    "cnblogs": ("博客园", "园", "#2c7a4b", "https://www.cnblogs.com/aggsite/topdigged24h", True, ()),
    "nodeseek": ("NodeSeek", "N", "#4e6e8e", "https://www.nodeseek.com/?tab=hot", True, ()),
    "tieba": ("百度贴吧", "贴", "#2f76c7", "https://tieba.baidu.com/", True, ()),
    "fuliba": ("福利吧", "福", "#d94c4c", "https://fuliba2023.net/", True, ()),
    "rss": ("RSS", "RSS", "#f28c28", "", True, ()),
}


_HIDDEN_BY_DEFAULT = {"maimai", "fuliba"}
_EXCLUDED_FROM_REPORT = {"maimai", "fuliba"}


CHANNELS: Dict[str, ChannelDefinition] = {
    channel_id: ChannelDefinition(
        channel_id=channel_id,
        name=values[0],
        order=index,
        short_name=values[1],
        color=values[2],
        collector=_lazy(channel_id),
        homepage=values[3],
        enabled_by_default=values[4],
        requires_env=values[5],
        frequency_minutes=CHANNEL_FREQUENCIES.get(channel_id, 60),
        visible_by_default=channel_id not in _HIDDEN_BY_DEFAULT,
        include_in_report=channel_id not in _EXCLUDED_FROM_REPORT,
    )
    for index, channel_id in enumerate(CHANNEL_ORDER, 1)
    for values in (_METADATA[channel_id],)
}


SPECIAL_CHANNELS = tuple(
    channel_id
    for channel_id in CHANNEL_ORDER
    if CHANNELS[channel_id].frequency_minutes != 60
    and CHANNELS[channel_id].enabled_by_default
)
HOURLY_CHANNELS = tuple(
    channel_id
    for channel_id in CHANNEL_ORDER
    if channel_id not in SPECIAL_CHANNELS and CHANNELS[channel_id].enabled_by_default
)


def get_channel(channel_id: str) -> ChannelDefinition:
    try:
        return CHANNELS[channel_id]
    except KeyError as exc:
        raise ValueError(f"unknown channel: {channel_id}") from exc


def iter_channels(enabled_only: bool = False) -> Iterable[ChannelDefinition]:
    channels = (CHANNELS[channel_id] for channel_id in CHANNEL_ORDER)
    if enabled_only:
        channels = (channel for channel in channels if channel.enabled_by_default)
    return channels


def resolve_channels(value) -> list:
    if isinstance(value, str) and value in {"hourly", "special"}:
        return list(HOURLY_CHANNELS if value == "hourly" else SPECIAL_CHANNELS)
    if value is None or value == "all" or value == ["all"]:
        return list(CHANNEL_ORDER)
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",") if part.strip()]
    else:
        values = list(value)
    unknown = [channel_id for channel_id in values if channel_id not in CHANNELS]
    if unknown:
        raise ValueError(f"unknown channel(s): {', '.join(unknown)}")
    return values
