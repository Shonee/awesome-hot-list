"""Build explainable daily reports from the existing append-only CSV archive."""

import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Mapping

from src.utils.file_utils import archive_path, read_csv

from .registry import CHANNEL_ORDER, get_channel, iter_channels


STOP_WORDS = {
    "一个", "一种", "这个", "那个", "这些", "那些", "什么", "怎么", "如何",
    "目前", "今天", "昨日", "表示", "回应", "视频", "热搜", "热榜", "网友",
    "热门", "网络", "发布", "可以", "进行", "相关", "常见", "为何", "中国",
    "更新", "为什么", "出来", "我的", "我们", "自己", "了吗", "数据", "展示",
}


def _rank(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _normalize_title(title: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(title or "").lower())


def _title_bigrams(value: str) -> set:
    return {value[index:index + 2] for index in range(max(0, len(value) - 1))}


def _similar_title(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 8:
        return False
    if left in right or right in left:
        return min(len(left), len(right)) / max(len(left), len(right)) >= 0.65
    left_terms = _title_bigrams(left)
    right_terms = _title_bigrams(right)
    shared = len(left_terms & right_terms)
    if shared < 5:
        return False
    return shared / len(left_terms | right_terms) >= 0.56


def _merge_topic_groups(grouped: Mapping[str, List[tuple]]) -> Dict[str, List[tuple]]:
    """Greedily merge small headline rewrites without an external NLP service."""
    merged: Dict[str, List[tuple]] = {}
    for normalized, occurrences in sorted(
        grouped.items(), key=lambda item: (-len(item[1]), -len(item[0]))
    ):
        target = next(
            (key for key in merged if _similar_title(key, normalized)),
            None,
        )
        if target is None:
            merged[normalized] = list(occurrences)
        else:
            merged[target].extend(occurrences)
    return merged


def _time_key(row: dict, date: str) -> str:
    value = str(row.get("datetime") or row.get("now_time") or date).strip()
    match = re.match(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})", value)
    return match.group(1).replace("T", " ") if match else (value or date)


def _time_label(value: str) -> str:
    match = re.search(r"(\d{2}):(\d{2})", value)
    return f"{match.group(1)}:{match.group(2)}" if match else value[-5:]


def _sample(values: List[str], limit: int = 5) -> List[str]:
    values = sorted(set(values))
    if len(values) <= limit:
        return values
    indexes = {round(index * (len(values) - 1) / (limit - 1)) for index in range(limit)}
    return [values[index] for index in sorted(indexes)]


def _hit(channel_id: str, row: dict) -> dict:
    return {
        "channelId": channel_id,
        "channelName": get_channel(channel_id).name,
        "ranking": row.get("type") or "热榜",
        "rank": _rank(row.get("index")) or None,
        "title": row.get("title") or "",
        "url": row.get("url") or "",
    }


def _unique_hits(rows: Iterable[tuple]) -> List[dict]:
    hits = []
    seen = set()
    for channel_id, row in rows:
        hit = _hit(channel_id, row)
        key = (hit["channelId"], hit["ranking"], hit["title"], hit["url"])
        if key in seen or not hit["url"]:
            continue
        seen.add(key)
        hits.append(hit)
    return hits[:30]


def _extract_keywords(records: List[tuple], limit: int = 40) -> List[tuple]:
    documents = list(
        dict.fromkeys(
            (channel_id, row.get("title", ""))
            for channel_id, row in records
            if row.get("title")
        )
    )
    titles = [title for _, title in documents]
    counts = Counter()
    channels = defaultdict(set)
    try:
        import jieba.analyse

        candidates = jieba.analyse.extract_tags("\n".join(titles), topK=limit * 3)
        for word in candidates:
            word = str(word).strip()
            if len(word) >= 2 and word not in STOP_WORDS and not word.isdigit():
                for channel_id, title in documents:
                    if word.lower() in title.lower():
                        counts[word] += 1
                        channels[word].add(channel_id)
    except ImportError:
        for channel_id, title in documents:
            terms = set(re.findall(r"[A-Za-z][A-Za-z0-9.+-]{1,14}", title))
            for segment in re.findall(r"[\u4e00-\u9fff]{2,}", title):
                for width in (2, 3, 4, 5):
                    terms.update(
                        segment[index:index + width]
                        for index in range(max(0, len(segment) - width + 1))
                    )
            for term in terms:
                if term in STOP_WORDS or term.isdigit():
                    continue
                counts[term] += 1
                channels[term].add(channel_id)
    ranked = sorted(
        counts.items(),
        key=lambda item: (-len(channels[item[0]]), -item[1], -len(item[0]), item[0]),
    )
    selected = []
    for term, count in ranked:
        if len(channels[term]) < 2 and len(selected) >= max(16, limit // 2):
            continue
        if any((term in chosen or chosen in term) and abs(chosen_count - count) <= 1 for chosen, chosen_count in selected):
            continue
        selected.append((term, count))
        if len(selected) >= limit:
            break
    return selected


def _track_state(ranks: List[int]) -> tuple:
    valid = [rank for rank in ranks if rank]
    if not valid:
        return "暂无变化", "steady"
    if len(valid) == 1:
        return "等待趋势", "pending"
    if ranks[0] is None or ranks[0] == 0:
        return "新上榜", "new"
    delta = valid[0] - valid[-1]
    if delta >= 5:
        return "持续上升", "up"
    if delta <= -5:
        return "持续下降", "down"
    if valid[-1] <= 5 and delta < 0:
        return "高位回落", "down"
    return "稳定在榜", "steady"


def _tenure(times: List[str]) -> str:
    if not times:
        return "暂无切片"
    if len(times) == 1:
        return "1 个切片"
    try:
        start = datetime.fromisoformat(times[0])
        end = datetime.fromisoformat(times[-1])
        hours = max(1, round((end - start).total_seconds() / 3600))
        return f"持续 {hours} 小时"
    except ValueError:
        return f"持续 {len(times)} 个切片"


def build_report_from_rows(date: str, rows_by_channel: Mapping[str, List[dict]]) -> dict:
    records = []
    slices = set()
    grouped = defaultdict(list)
    tracks = defaultdict(
        lambda: {
            "title": "",
            "channelId": "",
            "ranking": "",
            "times": defaultdict(list),
            "rows": [],
        }
    )

    for channel_id in CHANNEL_ORDER:
        for row in rows_by_channel.get(channel_id, []):
            title = str(row.get("title") or "").strip()
            normalized = _normalize_title(title)
            if not normalized:
                continue
            enriched = dict(row)
            enriched["title"] = title
            when = _time_key(row, date)
            records.append((channel_id, enriched))
            grouped[normalized].append((channel_id, enriched))
            ranking_name = row.get("type") or "热榜"
            slices.add((channel_id, ranking_name, when))
            track = tracks[(normalized, channel_id, ranking_name)]
            track["title"] = title
            track["channelId"] = channel_id
            track["ranking"] = ranking_name
            track["times"][when].append(_rank(row.get("index")))
            track["rows"].append((channel_id, enriched))

    grouped = _merge_topic_groups(grouped)

    topics = []
    for normalized, occurrences in grouped.items():
        channels = {channel_id for channel_id, _ in occurrences}
        valid_ranks = [_rank(row.get("index")) for _, row in occurrences]
        valid_ranks = [rank for rank in valid_ranks if rank]
        best_rank = min(valid_ranks) if valid_ranks else 50
        score = len(channels) * 100 + len(occurrences) * 4 + max(0, 51 - best_rank)
        hits = _unique_hits(occurrences)
        latest_title = occurrences[-1][1]["title"]
        topics.append(
            {
                "key": normalized,
                "title": latest_title,
                "source": "跨渠道" if len(channels) > 1 else get_channel(next(iter(channels))).name,
                "url": hits[0]["url"] if hits else "",
                "hits": hits,
                "score": score,
                "channelCount": len(channels),
            }
        )
    topics.sort(key=lambda item: (-item["score"], item["title"]))

    all_times = _sample([_time_key(row, date) for _, row in records])
    flow_rows = []
    track_candidates = sorted(
        tracks.items(),
        key=lambda item: (-len(item[1]["times"]), min((rank for ranks in item[1]["times"].values() for rank in ranks if rank), default=999)),
    )
    for _, track in track_candidates[:5]:
        row_times = _sample(list(track["times"]))
        ranks = []
        for when in row_times:
            values = [rank for rank in track["times"].get(when, []) if rank]
            ranks.append(min(values) if values else None)
        state, tone = _track_state(ranks)
        flow_rows.append(
            {
                "topic": track["title"],
                "query": track["title"],
                "source": get_channel(track["channelId"]).name,
                "ranking": track["ranking"],
                "tenure": _tenure(sorted(track["times"])),
                "times": [_time_label(value) for value in row_times],
                "ranks": ranks,
                "state": state,
                "tone": tone,
                "hits": _unique_hits(track["rows"]),
            }
        )

    words = []
    tones = ("hot", "teal", "gold", "")
    for index, (word, count) in enumerate(_extract_keywords(records)):
        matches = [(channel_id, row) for channel_id, row in records if word.lower() in row["title"].lower()]
        words.append(
            {
                "word": word,
                "weight": count,
                "tone": tones[index % len(tones)],
                "hits": _unique_hits(matches),
            }
        )

    resonance = sum(1 for topic in topics if topic["channelCount"] > 1)
    enabled_count = sum(1 for _ in iter_channels(enabled_only=True))
    active_count = sum(1 for channel_id in CHANNEL_ORDER if rows_by_channel.get(channel_id))
    max_rise = 0
    for row in flow_rows:
        valid = [rank for rank in row["ranks"] if rank]
        if len(valid) >= 2:
            max_rise = max(max_rise, valid[0] - valid[-1])

    signals = []
    for topic in [item for item in topics if item["channelCount"] > 1][:2]:
        signals.append(
            {
                "tag": "跨渠道",
                "title": topic["title"],
                "value": f"{topic['channelCount']} 渠道",
                "query": topic["title"],
                "hits": topic["hits"],
            }
        )
    signal_tags = {"up": "快速上升", "down": "持续下降", "steady": "持续在榜", "new": "新进入榜"}
    for row in flow_rows:
        if len(signals) >= 5:
            break
        if row["tone"] == "pending":
            continue
        signals.append(
            {
                "tag": signal_tags[row["tone"]],
                "title": row["topic"],
                "value": row["tenure"],
                "query": row["query"],
                "hits": row["hits"],
            }
        )

    lead = topics[0]["title"] if topics else "暂无足够数据"
    second = topics[1]["title"] if len(topics) > 1 else ""
    summary = (
        f"{lead}成为本期综合热度最高的话题"
        + (f"，{second}紧随其后" if second else "")
        + f"。当前覆盖 {active_count} 个有效渠道，共形成 {len(slices)} 个榜单时间切片；"
        + (f"发现 {resonance} 个跨渠道重复热点。" if resonance else "暂未发现标题完全一致的跨渠道热点。")
    )

    return {
        "schemaVersion": 1,
        "date": date,
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "metrics": {
            "deduplicated": len(topics),
            "resonance": resonance,
            "maxRise": max_rise,
            "slices": len(slices),
            "coverage": round(active_count / max(1, enabled_count) * 100),
        },
        "topTopics": [{key: value for key, value in topic.items() if key not in {"key", "score", "channelCount"}} for topic in topics[:10]],
        "words": words,
        "flow": {"times": [_time_label(value) for value in all_times], "rows": flow_rows},
        "signals": signals,
    }


def load_rows(date: str) -> Dict[str, List[dict]]:
    return {
        channel_id: read_csv(archive_path(channel_id, "csv", date))
        for channel_id in CHANNEL_ORDER
    }


def build_report(date: str) -> dict:
    return build_report_from_rows(date, load_rows(date))
