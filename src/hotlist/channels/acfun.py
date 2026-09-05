"""AcFun ranking adapter."""

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


BASE_URL = "https://www.acfun.cn/rest/pc-direct/rank/channel"
SOURCE_URL = "https://www.acfun.cn/rank/list/"


def parse_rank(payload: dict) -> list[HotItem]:
    rows = (payload or {}).get("rankList") or (payload or {}).get("data", {}).get("rankList", [])
    items = []
    for index, row in enumerate(rows, 1):
        title = row.get("contentTitle") or row.get("title")
        content_id = row.get("contentId") or row.get("dougaId")
        if title and content_id:
            items.append(HotItem(index, title, f"https://www.acfun.cn/v/ac{content_id}", hot=row.get("viewCount") or row.get("hotScore"), description=row.get("description") or "", image_url=row.get("coverUrl") or row.get("cover") or ""))
    return items


def collect() -> "ChannelSnapshot":
    headers = {"Referer": SOURCE_URL}
    rankings = []
    for ranking_id, name, period in (("day", "日榜", "DAY"), ("three-days", "三日榜", "THREE_DAYS"), ("week", "周榜", "WEEK")):
        url = f"{BASE_URL}?channelId=&subChannelId=&rankLimit=50&rankPeriod={period}"
        rankings.append(Ranking(ranking_id, name, parse_rank(get(url, res_type="json", headers=headers)), SOURCE_URL))
    return snapshot("acfun", rankings)
