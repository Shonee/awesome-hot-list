"""Validate channel data structures from the GitHub Actions runner network."""

import argparse
from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.hotlist.channels import eastmoney, googletrends, hackernews, huggingface, kuaishou, rss
from src.hotlist.channels import collect_channel
from src.hotlist.channels.dailyhot import fetch_payload as fetch_dailyhot
from src.hotlist.channels.tophub import fetch_ranking as fetch_tophub_ranking
from src.hotlist.models import ChannelSnapshot
from src.utils.http_utils import get, post


@dataclass(frozen=True)
class Probe:
    run: Callable[[], int]
    minimum: int = 5
    required: bool = True


SKIPPED_SOURCES = {
    "bing": (
        "no stable non-RSS Bing trend source identified; the official Bing Search API "
        "is retired and a normal search result page is not a popularity ranking"
    ),
}


def count_snapshot_items(snapshot: ChannelSnapshot) -> int:
    return sum(len(ranking.items) for ranking in snapshot.rankings)


def require_items(probe_id: str, count: int, minimum: int = 5) -> int:
    if count < minimum:
        raise RuntimeError(f"{probe_id} returned only {count} valid item(s), expected at least {minimum}")
    return count


def _collect(channel_id: str, require_every_ranking: bool = False) -> int:
    snapshot = collect_channel(channel_id)
    if snapshot.status != "ok":
        raise RuntimeError(f"collector status is {snapshot.status}: {snapshot.error}")
    if require_every_ranking:
        for ranking in snapshot.rankings:
            require_items(f"{channel_id}/{ranking.ranking_id}", len(ranking.items))
    return count_snapshot_items(snapshot)


def _hackernews_api() -> int:
    story_ids = get(hackernews.TOP_STORIES_URL, res_type="json", timeout=20, retries=1)
    valid = 0
    for story_id in list(story_ids or [])[:5]:
        row = get(
            hackernews.ITEM_URL.format(story_id=story_id),
            res_type="json",
            timeout=12,
            retries=1,
        )
        valid += int(hackernews.parse_story(row, valid + 1) is not None)
    return valid


def _huggingface_api() -> int:
    payload = get(huggingface.API_URL, res_type="json", timeout=25, retries=1)
    return len(huggingface.parse_models(payload))


def _google_trends_page() -> int:
    html = get(googletrends.SOURCE_URL, timeout=30, retries=1)
    return len(googletrends.parse_trending_page(html))


def _kuaishou_official_page() -> int:
    html = get(kuaishou.SOURCE_URL, headers=kuaishou.HEADERS, timeout=25, retries=1)
    return len(kuaishou.parse_official_page(html))


def _kuaishou_dailyhot() -> int:
    return len(kuaishou.parse_dailyhot(fetch_dailyhot(kuaishou.DAILYHOT_URL)))


def _eastmoney_quotes() -> int:
    rank_payload = post(
        eastmoney.RANK_API,
        payload=eastmoney.RANK_PAYLOAD,
        res_type="json",
        timeout=20,
        retries=1,
    )
    security_ids = [
        eastmoney._security_id(row.get("sc"))
        for row in (rank_payload or {}).get("data") or []
        if isinstance(row, dict)
    ]
    query = urlencode({"secids": ",".join(filter(None, security_ids)), "fields": "f12,f14,f2,f3"})
    quote_payload = get(f"{eastmoney.QUOTE_API}?{query}", res_type="json", timeout=20, retries=1)
    return len(eastmoney._quote_map(quote_payload))


def _linuxdo_rss() -> int:
    url = "https://linux.do/top.rss?period=weekly"
    _name, items = rss.parse_feed(get(url, timeout=20, retries=1), url)
    return len(items)


PROBES = {
    "baidu": Probe(lambda: _collect("baidu")),
    "netease": Probe(lambda: _collect("netease")),
    "sina": Probe(lambda: _collect("sina", require_every_ranking=True), minimum=10),
    "eastmoney": Probe(lambda: _collect("eastmoney")),
    "eastmoney-quotes": Probe(_eastmoney_quotes, required=False),
    "hackernews": Probe(_hackernews_api),
    "thepaper": Probe(lambda: _collect("thepaper")),
    "lobsters": Probe(lambda: _collect("lobsters")),
    "huggingface": Probe(_huggingface_api),
    "googletrends": Probe(_google_trends_page),
    "kuaishou": Probe(lambda: _collect("kuaishou")),
    "kuaishou-official": Probe(_kuaishou_official_page, required=False),
    "dailyhot-kuaishou": Probe(_kuaishou_dailyhot, required=False),
    "cnblogs": Probe(lambda: _collect("cnblogs")),
    "linuxdo": Probe(_linuxdo_rss, required=False),
    "nodeseek": Probe(lambda: _collect("nodeseek")),
    "pojie52": Probe(lambda: _collect("pojie52")),
    "qqnews": Probe(lambda: _collect("qqnews")),
    "tieba": Probe(lambda: _collect("tieba")),
    "tophub-zhihu": Probe(
        lambda: len(fetch_tophub_ranking(
            "https://tophub.today/n/mproPpoq6O", ("zhihu.com",), min_items=1
        ))
    ),
    "tophub-wechat": Probe(
        lambda: len(fetch_tophub_ranking(
            "https://tophub.today/n/WnBe01o371", ("mp.weixin.qq.com",), min_items=1
        ))
    ),
    "tophub-kuaishou": Probe(
        lambda: len(fetch_tophub_ranking(
            kuaishou.TOPHUB_URL, ("kuaishou.com",), min_items=1
        ))
    ),
    "xueqiu": Probe(lambda: _collect("xueqiu")),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 GitHub Actions 网络中的渠道有效数据")
    choices = tuple(PROBES) + tuple(SKIPPED_SOURCES)
    parser.add_argument("channels", nargs="*", choices=choices)
    args = parser.parse_args()
    channels = args.channels or list(PROBES) + list(SKIPPED_SOURCES)
    failed = 0
    for channel_id in channels:
        if channel_id in SKIPPED_SOURCES:
            print(f"[skip] {channel_id}: {SKIPPED_SOURCES[channel_id]}")
            continue
        probe = PROBES[channel_id]
        try:
            count = require_items(channel_id, probe.run(), probe.minimum)
            print(f"[ok]   {channel_id}: {count} valid item(s)")
        except Exception as exc:  # noqa: BLE001 - report every endpoint independently
            if probe.required:
                failed += 1
                print(f"[fail] {channel_id}: {exc}")
            else:
                print(f"[warn] {channel_id}: optional source unavailable: {exc}")
    if failed:
        print(f"{failed} probe(s) failed structural validation", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
