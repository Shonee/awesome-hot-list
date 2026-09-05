# -*- coding: utf-8 -*-
"""Generate the static dashboard and daily report JSON files."""

import glob
import logging
import os
import re
import shutil
import sys
import time


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir)
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.hotlist.models import ChannelSnapshot, Ranking, items_from_legacy
from src.hotlist.registry import CHANNEL_ORDER, get_channel
from src.hotlist.report import build_report, load_rows
from src.hotlist.runner import merge_latest_snapshot
from src.utils.file_utils import current_date, read_csv, write_json, yesterday_date


logger = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s", level=logging.INFO)


def _write_enabled() -> bool:
    return os.environ.get("HOTLIST_WRITE", "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


def _timestamp(row: dict, fallback: str) -> str:
    """Return the collection timestamp, never an item's publication time."""
    return str(row.get("datetime") or row.get("now_time") or fallback).strip()


def _latest_from_rows(date: str, rows_by_channel: dict) -> list:
    """Build channel snapshots from the newest archived slice of each ranking."""
    snapshots = []
    for channel_id in CHANNEL_ORDER:
        rows = rows_by_channel.get(channel_id, [])
        if not rows:
            continue

        slices_by_ranking = {}
        for row in rows:
            name = row.get("type") or "热榜"
            fetched_at = _timestamp(row, date)
            slices_by_ranking.setdefault(name, {}).setdefault(fetched_at, []).append(row)

        rankings = []
        latest_channel_time = ""
        for index, (name, slices) in enumerate(slices_by_ranking.items(), 1):
            latest_time = max(slices)
            latest_channel_time = max(latest_channel_time, latest_time)
            ranking_id = re.sub(r"[^0-9a-z]+", "-", name.lower()).strip("-")
            rankings.append(
                Ranking(
                    ranking_id or f"ranking-{index}",
                    name,
                    items_from_legacy(slices[latest_time]),
                )
            )

        definition = get_channel(channel_id)
        snapshots.append(
            ChannelSnapshot(
                channel_id=channel_id,
                channel_name=definition.name,
                source_url=definition.homepage,
                fetched_at=latest_channel_time or date,
                rankings=rankings,
            )
        )
    return snapshots


def _latest_available_rows() -> dict:
    """Read each channel's newest CSV when today's archive is still empty."""
    rows_by_channel = {}
    for channel_id in CHANNEL_ORDER:
        pattern = os.path.join(
            PROJECT_ROOT, "archived", channel_id, "*", "*", "csv", "*.csv"
        )
        candidates = sorted(glob.glob(pattern))
        rows_by_channel[channel_id] = read_csv(candidates[-1]) if candidates else []
    return rows_by_channel


def _ensure_latest_snapshot(today: str, today_rows: dict, latest_path: str) -> None:
    if os.path.isfile(latest_path):
        return

    fallback_rows = today_rows if any(today_rows.values()) else _latest_available_rows()
    snapshots = _latest_from_rows(today, fallback_rows)
    known_ids = {snapshot.channel_id for snapshot in snapshots}
    for channel_id in CHANNEL_ORDER:
        if channel_id in known_ids:
            continue
        definition = get_channel(channel_id)
        snapshots.append(
            ChannelSnapshot.unavailable(
                channel_id,
                definition.name,
                definition.homepage,
                time.strftime("%Y-%m-%d %H:%M:%S"),
                "unavailable",
                "not collected yet",
            )
        )
    merge_latest_snapshot(snapshots, latest_path, channel_order=CHANNEL_ORDER)


def main() -> None:
    today = current_date()
    previous = yesterday_date()
    logger.info("生成正式站点：今日 %s，历史 %s", today, previous)

    today_rows = load_rows(today)
    today_report = build_report(today)
    previous_report = build_report(previous)
    if not _write_enabled():
        logger.info("当前为调试模式（HOTLIST_WRITE=0），只分析不落盘")
        return

    reports_dir = os.path.join(PROJECT_ROOT, "site", "data", "reports")
    write_json(today_report, os.path.join(reports_dir, "today.json"), atomic=True)
    write_json(previous_report, os.path.join(reports_dir, "previous.json"), atomic=True)
    write_json(previous_report, os.path.join(reports_dir, f"{previous}.json"), atomic=True)

    latest_path = os.path.join(PROJECT_ROOT, "site", "data", "latest.json")
    _ensure_latest_snapshot(today, today_rows, latest_path)

    template_path = os.path.join(PROJECT_ROOT, "src", "template", "site.html")
    output_path = os.path.join(PROJECT_ROOT, "site", "index.html")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    shutil.copyfile(template_path, output_path)
    logger.info(
        "站点已生成：%s（今日 %d 条去重热点，昨日 %d 条）",
        output_path,
        today_report["metrics"]["deduplicated"],
        previous_report["metrics"]["deduplicated"],
    )


if __name__ == "__main__":
    main()
