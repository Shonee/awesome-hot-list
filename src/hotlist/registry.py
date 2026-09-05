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


CHANNEL_ORDER = (
    "bilibili",
    "douyin",
    "weibo",
    "zhihu",
    "github",
    "juejin",
    "toutiao",
    "acfun",
    "ithome",
    "douban",
    "hupu",
    "36kr",
    "tonghuashun",
    "maimai",
    "xueqiu",
    "v2ex",
    "stackoverflow",
    "cls",
    "rss",
)

# GitHub Actions checks special channels hourly, but the collector only runs a
# channel when this interval has elapsed since its last snapshot. This keeps
# one scheduling model while allowing less stable or slower sources to opt out
# of a full hourly request.
CHANNEL_FREQUENCIES = {
    "github": 360,
    "zhihu": 360,
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
    "bilibili": ("哔哩哔哩", "BILI", "#fb7299", "https://www.bilibili.com/v/popular/all", True, ()),
    "douyin": ("抖音", "DY", "#161823", "https://www.douyin.com/hot", True, ()),
    "weibo": ("微博", "WB", "#e6162d", "https://s.weibo.com/top/summary", True, ()),
    "zhihu": ("知乎", "ZH", "#1772f6", "https://www.zhihu.com/hot", False, ("ZHIHU_COOKIE",)),
    "github": ("GitHub", "GH", "#24292f", "https://github.com/trending", True, ()),
    "juejin": ("掘金", "掘", "#1e80ff", "https://juejin.cn/hot/articles", True, ()),
    "toutiao": ("今日头条", "TT", "#f04142", "https://www.toutiao.com/hot-event/hot-board/", True, ()),
    "rss": ("RSS", "RSS", "#f28c28", "", True, ()),
    "acfun": ("AcFun", "AC", "#fd4c5d", "https://www.acfun.cn/rank/list/", True, ()),
    "ithome": ("IT之家", "IT", "#d22222", "https://www.ithome.com/", True, ()),
    "douban": ("豆瓣", "DB", "#00a65a", "https://movie.douban.com/chart", True, ()),
    "hupu": ("虎扑", "HP", "#b31b1b", "https://bbs.hupu.com/all-gambia", True, ()),
    "36kr": ("36氪", "36", "#0066ff", "https://www.36kr.com/hot-list/catalog", True, ()),
    "tonghuashun": ("同花顺", "THS", "#e83b35", "https://t.10jqka.com.cn/", True, ()),
    "maimai": ("脉脉", "MM", "#00a6a6", "https://maimai.cn/web/gossip_list", False, ("MAIMAI_COOKIE",)),
    "xueqiu": ("雪球", "XQ", "#1f6fb2", "https://xueqiu.com/today", False, ()),
    "v2ex": ("V2EX", "V2", "#778087", "https://www.v2ex.com/?tab=hot", True, ()),
    "stackoverflow": ("Stack Overflow", "SO", "#f48024", "https://stackoverflow.com/questions?tab=hot", True, ()),
    "cls": ("财联社", "财", "#c72b2b", "https://www.cls.cn/telegraph", True, ()),
}


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
    )
    for index, (channel_id, values) in enumerate(_METADATA.items(), 1)
}


SPECIAL_CHANNELS = tuple(
    channel_id for channel_id in CHANNEL_ORDER if CHANNELS[channel_id].frequency_minutes != 60
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
