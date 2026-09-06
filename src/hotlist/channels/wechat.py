"""WeChat public-article hot list backed by TodayHot."""

from ..models import Ranking
from .common import snapshot
from .tophub import fetch_ranking as fetch_tophub_ranking


TOPHUB_WECHAT_URL = "https://tophub.today/n/WnBe01o371"


def collect() -> "ChannelSnapshot":
    items = fetch_tophub_ranking(
        TOPHUB_WECHAT_URL,
        allowed_hosts=("mp.weixin.qq.com",),
        limit=50,
        min_items=5,
    )
    return snapshot(
        "wechat",
        [
            Ranking(
                "articles_24h",
                "24h 热文榜",
                items,
                TOPHUB_WECHAT_URL,
                provider_name="今日热榜",
                provider_url=TOPHUB_WECHAT_URL,
            )
        ],
    )
