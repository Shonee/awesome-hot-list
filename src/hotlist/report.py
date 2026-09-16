"""Build explainable daily reports from the existing append-only CSV archive."""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from math import ceil
from typing import Dict, Iterable, List, Mapping

from src.utils.file_utils import archive_path, read_csv
from src.utils.time_utils import now_string, project_now

from .registry import CHANNEL_ORDER, get_channel, iter_channels


STOP_WORDS = {
    "一个", "一种", "这个", "那个", "这些", "那些", "什么", "怎么", "如何",
    "目前", "今天", "昨日", "表示", "回应", "视频", "热搜", "热榜", "网友",
    "热门", "网络", "发布", "可以", "进行", "相关", "常见", "为何", "中国",
    "更新", "为什么", "出来", "我的", "我们", "自己", "了吗", "数据", "展示",
    "为什", "了一", "的是", "是在", "以及", "其中", "对于", "通过", "之后",
    "真的", "这么",
}


def _is_noise_term(term: str) -> bool:
    if (
        len(term) < 2
        or term.isdigit()
        or term in STOP_WORDS
        or not re.search(r"[0-9A-Za-z\u4e00-\u9fff]", term)
    ):
        return True
    return any(term in stop_word for stop_word in STOP_WORDS if len(stop_word) > len(term))


def _rank(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _included_channel_ids() -> tuple[str, ...]:
    """Return report channels while remaining compatible with older registries."""
    return tuple(
        channel_id
        for channel_id in CHANNEL_ORDER
        if getattr(get_channel(channel_id), "include_in_report", True)
    )


def _rank_percentile(rank: int, ranking_length: int) -> float:
    """Normalize a rank to 0..1 so differently sized lists are comparable."""
    if rank <= 0:
        return 0.0
    if ranking_length <= 1:
        return 1.0
    return max(0.0, min(1.0, 1 - (rank - 1) / (ranking_length - 1)))


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


def _comparison_topic(topic: dict, current_rank=None, previous_rank=None) -> dict:
    current_rank = _rank(current_rank) or None
    previous_rank = _rank(previous_rank) or None
    return {
        "title": topic.get("title") or "",
        "source": topic.get("source") or "",
        "url": topic.get("url") or "",
        "query": topic.get("title") or "",
        "hits": topic.get("hits") or [],
        "currentRank": current_rank,
        "previousRank": previous_rank,
        "delta": previous_rank - current_rank if current_rank and previous_rank else None,
    }


def add_day_comparison(report: dict, previous_report: dict) -> dict:
    """Compare two Top-10 reports using the same fuzzy title matching as clustering."""
    current_topics = list(report.get("topTopics", []))[:10]
    previous_topics = list(previous_report.get("topTopics", []))[:10]
    previous_keys = [_normalize_title(topic.get("title")) for topic in previous_topics]
    unmatched_previous = set(range(len(previous_topics)))
    new_topics = []
    continued_topics = []
    rising_topics = []
    falling_topics = []

    for current_index, topic in enumerate(current_topics):
        current_key = _normalize_title(topic.get("title"))
        exact = [
            index
            for index in unmatched_previous
            if current_key and current_key == previous_keys[index]
        ]
        similar = [
            index
            for index in unmatched_previous
            if current_key and _similar_title(current_key, previous_keys[index])
        ]
        candidates = exact or similar
        if not candidates:
            new_topics.append(_comparison_topic(topic, current_index + 1))
            continue

        previous_index = min(candidates, key=lambda index: abs(index - current_index))
        unmatched_previous.remove(previous_index)
        item = _comparison_topic(topic, current_index + 1, previous_index + 1)
        continued_topics.append(item)
        if item["delta"] > 0:
            rising_topics.append(item)
        elif item["delta"] < 0:
            falling_topics.append(item)

    dropped_topics = [
        _comparison_topic(topic, previous_rank=index + 1)
        for index, topic in enumerate(previous_topics)
        if index in unmatched_previous
    ]
    report["dayComparison"] = {
        "baselineDate": previous_report.get("date") or "",
        "counts": {
            "new": len(new_topics),
            "continued": len(continued_topics),
            "rising": len(rising_topics),
            "falling": len(falling_topics),
            "dropped": len(dropped_topics),
        },
        "new": new_topics,
        "continued": continued_topics,
        "rising": rising_topics,
        "falling": falling_topics,
        "dropped": dropped_topics,
    }
    return report


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


def _topic_freshness(sample_keys: set, ranking_slices: Mapping[tuple, set]) -> float:
    """Measure whether a topic still appears in each source's latest sample."""
    values = []
    ranking_keys = {sample[:2] for sample in sample_keys}
    for ranking_key in ranking_keys:
        timeline = sorted(ranking_slices[ranking_key])
        topic_times = {sample[2] for sample in sample_keys if sample[:2] == ranking_key}
        if not timeline or not topic_times:
            continue
        if len(timeline) == 1:
            values.append(1.0)
            continue
        latest_index = timeline.index(max(topic_times))
        values.append(latest_index / (len(timeline) - 1))
    return sum(values) / max(1, len(values))


def _sampling_coverage(date: str, records: List[tuple], enabled_channels: List[object]) -> int:
    """Return successful scheduled samples as a percentage of expected samples."""
    try:
        report_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return 0

    now = project_now()
    if report_date > now.date():
        elapsed_minutes = 0
    elif report_date == now.date():
        elapsed_minutes = now.hour * 60 + now.minute + 1
    else:
        elapsed_minutes = 24 * 60

    actual_times = defaultdict(set)
    for channel_id, row in records:
        actual_times[channel_id].add(_time_key(row, date))

    expected_total = 0
    actual_total = 0
    for channel in enabled_channels:
        interval = max(1, int(getattr(channel, "frequency_minutes", 60)))
        expected = ceil(elapsed_minutes / interval) if elapsed_minutes else 0
        expected_total += expected
        actual_total += min(expected, len(actual_times[channel.channel_id]))
    return round(actual_total / max(1, expected_total) * 100)


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
    seen = defaultdict(list)
    for channel_id, row in rows:
        hit = _hit(channel_id, row)
        title = _normalize_title(hit["title"])
        if not hit["url"] or any(_similar_title(title, previous) for previous in seen[channel_id]):
            continue
        seen[channel_id].append(title)
        hits.append(hit)
        if len(hits) == 30:
            break
    return hits


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
            if not _is_noise_term(word):
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
                if _is_noise_term(term):
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
        if len(ranks) > 1 and ranks[-1] is None:
            return "已掉榜", "dropped"
        if len(ranks) > 1 and ranks[0] is None:
            return "新上榜", "new"
        return "等待趋势", "pending"
    if ranks[-1] is None:
        return "已掉榜", "dropped"
    first_seen = next((index for index, rank in enumerate(ranks) if rank), None)
    if first_seen is not None and any(rank is None for rank in ranks[first_seen + 1:-1]):
        return "重新上榜", "reentered"
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


def _tenure(times: List[str], observed: int | None = None) -> str:
    if not times:
        return "暂无切片"
    if observed is not None and observed < len(times):
        return f"在榜 {observed}/{len(times)} 个切片"
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
    included_channel_ids = _included_channel_ids()
    enabled_channels = [
        channel
        for channel in iter_channels(enabled_only=True)
        if getattr(channel, "include_in_report", True)
    ]
    enabled_ids = {channel.channel_id for channel in enabled_channels}
    records = []
    slices = set()
    grouped = defaultdict(list)
    ranking_slices = defaultdict(set)
    ranking_lengths = defaultdict(int)
    tracks = defaultdict(
        lambda: {
            "title": "",
            "channelId": "",
            "ranking": "",
            "times": defaultdict(list),
            "rows": [],
        }
    )

    for channel_id in included_channel_ids:
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
            ranking_slices[(channel_id, ranking_name)].add(when)
            ranking_lengths[(channel_id, ranking_name, when)] = max(
                ranking_lengths[(channel_id, ranking_name, when)],
                _rank(row.get("index")),
            )
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
        rank_percentiles = []
        for channel_id, row in occurrences:
            ranking_name = row.get("type") or "热榜"
            when = _time_key(row, date)
            rank_percentiles.append(
                _rank_percentile(
                    _rank(row.get("index")),
                    ranking_lengths[(channel_id, ranking_name, when)],
                )
            )
        rank_quality = sum(rank_percentiles) / max(1, len(rank_percentiles))
        sample_keys = {
            (channel_id, row.get("type") or "热榜", _time_key(row, date))
            for channel_id, row in occurrences
        }
        ranking_keys = {(channel_id, row.get("type") or "热榜") for channel_id, row in occurrences}
        persistence = sum(
            sum(1 for sample in sample_keys if sample[:2] == ranking_key)
            / max(1, len(ranking_slices[ranking_key]))
            for ranking_key in ranking_keys
        ) / max(1, len(ranking_keys))
        freshness = _topic_freshness(sample_keys, ranking_slices)
        # Resonance has the largest weight and reaches full value at three
        # channels. The remaining factors distinguish topics without turning
        # absolute list length or old repeated samples into a permanent lead.
        channel_reach = min(1.0, len(channels) / 3)
        score = round(
            (
                channel_reach * 0.70
                + rank_quality * 0.15
                + persistence * 0.10
                + freshness * 0.05
            )
            * 10_000
        )
        hits = _unique_hits(occurrences)
        latest_title = max(occurrences, key=lambda item: _time_key(item[1], date))[1]["title"]
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
    track_candidates = []
    tone_priority = {"dropped": 4, "new": 4, "reentered": 4, "up": 3, "down": 3, "steady": 1, "pending": 0}
    for _, track in tracks.items():
        timeline = sorted(ranking_slices[(track["channelId"], track["ranking"])])
        full_ranks = []
        for when in timeline:
            values = [rank for rank in track["times"].get(when, []) if rank]
            full_ranks.append(min(values) if values else None)
        state, tone = _track_state(full_ranks)
        valid = [rank for rank in full_ranks if rank]
        movement = abs(valid[0] - valid[-1]) if len(valid) >= 2 else 0
        track_candidates.append((tone_priority[tone], movement, len(valid), min(valid, default=999), track, timeline, full_ranks, state, tone))

    track_candidates.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]["title"]))
    flow_rows = []
    for _, _, observed, _, track, timeline, full_ranks, state, tone in track_candidates[:5]:
        row_times = _sample(timeline)
        rank_by_time = dict(zip(timeline, full_ranks))
        ranks = [rank_by_time[when] for when in row_times]
        state, tone = _track_state(ranks)
        flow_rows.append(
            {
                "topic": track["title"],
                "query": track["title"],
                "source": get_channel(track["channelId"]).name,
                "ranking": track["ranking"],
                "tenure": _tenure(timeline, observed),
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
    active_count = sum(1 for channel_id in included_channel_ids if rows_by_channel.get(channel_id))
    max_rise = 0
    for _, _, _, _, _, _, ranks, _, _ in track_candidates:
        valid = [rank for rank in ranks if rank]
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
    signal_tags = {"up": "快速上升", "down": "持续下降", "steady": "持续在榜", "new": "新进入榜", "dropped": "已掉榜", "reentered": "重新上榜"}
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
        "generatedAt": now_string(),
        "summary": summary,
        "metrics": {
            "deduplicated": len(topics),
            "resonance": resonance,
            "maxRise": max_rise,
            "slices": len(slices),
            "coverage": round(
                sum(1 for channel_id in enabled_ids if rows_by_channel.get(channel_id))
                / max(1, len(enabled_ids))
                * 100
            ),
            "samplingCoverage": _sampling_coverage(date, records, enabled_channels),
        },
        "topTopics": [{key: value for key, value in topic.items() if key not in {"key", "score", "channelCount"}} for topic in topics[:10]],
        "words": words,
        "flow": {"times": [_time_label(value) for value in all_times], "rows": flow_rows},
        "signals": signals,
    }


def load_rows(date: str) -> Dict[str, List[dict]]:
    return {
        channel_id: read_csv(archive_path(channel_id, "csv", date))
        for channel_id in _included_channel_ids()
    }


def build_report(date: str) -> dict:
    report = build_report_from_rows(date, load_rows(date))
    previous_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    previous_report = build_report_from_rows(previous_date, load_rows(previous_date))
    return add_day_comparison(report, previous_report)
