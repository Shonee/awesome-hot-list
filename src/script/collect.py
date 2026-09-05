# -*- coding: utf-8 -*-
"""Unified command-line entry for one, many, or all hot-list channels."""

import argparse
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.hotlist.registry import CHANNEL_ORDER, resolve_channels
from src.hotlist.report import build_report
from src.hotlist.runner import collect_channels, due_channel_ids, merge_latest_snapshot
from src.utils.file_utils import archive_path, channel_readme_path, current_date, write_csv, write_json, write_text
from src.utils.utils import load_dotenv


DEFAULT_LATEST_PATH = os.path.join("site", "data", "latest.json")


def _write_enabled() -> bool:
    return os.environ.get("HOTLIST_WRITE", "1").strip().lower() not in {"0", "false", "no", "off"}


def _markdown(snapshot) -> str:
    lines = [
        f"# {snapshot.channel_name}热榜",
        "",
        f"> 更新时间：{snapshot.fetched_at}",
        "",
    ]
    for ranking in snapshot.rankings:
        lines.extend([f"## {ranking.name}", ""])
        lines.extend(
            f"{item.rank}. [{item.title}]({item.url})"
            for item in ranking.items
        )
        lines.append("")
    return "\n".join(lines)


def write_channel_archive(snapshot) -> None:
    if snapshot.status != "ok":
        return
    date = snapshot.fetched_at[:10] or time.strftime("%Y-%m-%d")
    rows = snapshot.to_legacy_rows()
    if rows:
        write_csv(rows, archive_path(snapshot.channel_id, "csv", date), mode="append", atomic=True)
    write_text(_markdown(snapshot), channel_readme_path(snapshot.channel_id), atomic=True)


def run(channel_value: str, latest_path: str = DEFAULT_LATEST_PATH, due_only: bool = False):
    channel_ids = resolve_channels(channel_value)
    if due_only:
        channel_ids = due_channel_ids(channel_ids, latest_path)
        if not channel_ids:
            print("[skip] no channels are due")
            return []
    snapshots = collect_channels(channel_ids)
    if _write_enabled():
        for snapshot in snapshots:
            write_channel_archive(snapshot)
        merge_latest_snapshot(snapshots, latest_path, channel_order=CHANNEL_ORDER)
        write_json(
            build_report(current_date()),
            os.path.join("site", "data", "reports", "today.json"),
            atomic=True,
        )

    for snapshot in snapshots:
        count = sum(len(ranking.items) for ranking in snapshot.rankings)
        detail = f" ({snapshot.error})" if snapshot.error else ""
        print(f"[{snapshot.status}] {snapshot.channel_id}: {count} items{detail}")
    return snapshots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="采集一个、多个或全部热榜渠道")
    parser.add_argument(
        "channels",
        nargs="?",
        default="all",
        help="渠道 ID、逗号分隔的多个 ID，或 all",
    )
    parser.add_argument("--latest-path", default=DEFAULT_LATEST_PATH, help="统一最新快照 JSON 路径")
    parser.add_argument(
        "--due",
        action="store_true",
        help="只采集达到各自频率间隔的渠道，适合每小时调度的特殊渠道任务",
    )
    return parser


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()
    snapshots = run(args.channels, args.latest_path, due_only=args.due)
    return 0 if not snapshots or any(snapshot.status == "ok" for snapshot in snapshots) else 1


if __name__ == "__main__":
    raise SystemExit(main())
