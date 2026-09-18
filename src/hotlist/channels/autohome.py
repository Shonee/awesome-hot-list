"""Autohome's official daily hot-topic ranking."""

from urllib.parse import urlparse

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import same_host, snapshot


SOURCE_URL = "https://www.autohome.com.cn/cars/hotrank/1"
RANK_API_URL = "https://www.autohome.com.cn/web-main/car/web/hotRank/getList?type=1"


def parse_hot_rank(payload: dict) -> list[HotItem]:
    rows = payload.get("result", {}).get("rankList", []) if isinstance(payload, dict) else []
    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        host = (urlparse(url).hostname or "").lower()
        if not title or not (same_host(url, {"autohome.com.cn", host}) and (host == "autohome.com.cn" or host.endswith(".autohome.com.cn"))) or url in seen:
            continue
        seen.add(url)
        items.append(HotItem(row.get("rank") or len(items) + 1, title, url, hot=row.get("hotScore"),
                             description=row.get("subTitle") or "", image_url=row.get("img") or ""))
        if len(items) >= 50:
            break
    return items


def collect() -> "ChannelSnapshot":
    payload = get(RANK_API_URL, res_type="json", headers={"Referer": SOURCE_URL}, timeout=20, retries=1)
    return snapshot("autohome", [Ranking("daily-hot", "每日热点榜", parse_hot_rank(payload),
                                         SOURCE_URL, "汽车之家官方", RANK_API_URL)])
