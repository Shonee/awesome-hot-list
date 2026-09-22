# -*- coding: utf-8 -*-
"""Unified command-line entry for one, many, or all hot-list channels."""

import argparse
from contextlib import contextmanager
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.hotlist.registry import CHANNEL_ORDER, resolve_channels
from src.hotlist.runner import collect_channels, due_channel_ids, write_surface_snapshots
from src.utils.file_utils import archive_path, channel_readme_path, current_date, write_csv, write_text
from src.utils.utils import load_dotenv


DEFAULT_LATEST_PATH = os.path.join("site", "data", "latest.json")


@contextmanager
def _use_data_root(data_root: str):
    root = os.path.abspath(data_root)
    os.makedirs(root, exist_ok=True)
    previous = os.getcwd()
    os.chdir(root)
    try:
        yield root
    finally:
        os.chdir(previous)


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
    date = snapshot.fetched_at[:10] or current_date()
    rows = snapshot.to_legacy_rows()
    if rows:
        write_csv(rows, archive_path(snapshot.channel_id, "csv", date), mode="append", atomic=True)
    write_text(_markdown(snapshot), channel_readme_path(snapshot.channel_id), atomic=True)


def run(
    channel_value: str,
    latest_path: str = DEFAULT_LATEST_PATH,
    due_only: bool = False,
    data_root: str = ".",
    surface: str = "",
):
    with _use_data_root(data_root):
        channel_ids = resolve_channels(channel_value)
        if due_only:
            channel_ids = due_channel_ids(channel_ids, latest_path)
            if not channel_ids:
                print("[skip] no channels are due")
                return []
        snapshots = collect_channels(channel_ids, surface=surface)
        if _write_enabled():
            write_surface_snapshots(
                snapshots,
                latest_path,
                requested_surface=surface,
                channel_order=CHANNEL_ORDER,
            )
            for snapshot in snapshots:
                try:
                    write_channel_archive(snapshot)
                except OSError as exc:
                    # 页面快照已落盘；单渠道归档读不到旧 CSV 时跳过该渠道，
                    # 而不是让整批采集陪葬，也绝不静默覆盖已有内容。
                    print(f"[warn] {snapshot.channel_id}: archive skipped: {exc}")

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
    parser.add_argument(
        "--surface",
        choices=("hotlist", "live", "digest", "authority"),
        default="",
        help="只归档并合并指定内容面；用于 15 分钟快讯局部刷新",
    )
    parser.add_argument("--latest-path", default=DEFAULT_LATEST_PATH, help="热榜快照 JSON 路径；其他内容面使用同目录独立文件")
    parser.add_argument(
        "--data-root",
        default=os.environ.get("HOTLIST_DATA_ROOT", "."),
        help="归档和 site 产物根目录；CI 使用独立的 data-pages 工作区",
    )
    parser.add_argument(
        "--due",
        action="store_true",
        help="只采集达到各自频率间隔的渠道，适合每小时调度的特殊渠道任务",
    )
    return parser


def _failure_summary(snapshots) -> dict:
    attempted = [snapshot for snapshot in snapshots if snapshot.status != "disabled"]
    failed = [snapshot for snapshot in attempted if snapshot.status == "error"]
    error_types = {}
    for snapshot in failed:
        key = (snapshot.health or {}).get("errorType") or "unknown"
        error_types[key] = error_types.get(key, 0) + 1
    return {
        "attempted": len(attempted),
        "failed": len(failed),
        "failedChannels": [snapshot.channel_id for snapshot in failed],
        "errorTypes": error_types,
    }


def _env_number(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _exit_code_for_snapshots(snapshots) -> int:
    """Fail when a batch is broken, not when one flaky source hiccuped.

    单个渠道失败是常态，每天都红会淹掉真正的事故，所以比例和绝对数要同时越界；
    全军覆没则与批次大小无关，一定是事故。
    """
    summary = _failure_summary(snapshots)
    if not summary["attempted"]:
        return 0
    if summary["failed"] == summary["attempted"]:
        return 1
    ratio = _env_number("HOTLIST_FAILURE_RATIO", 0.5)
    minimum = _env_number("HOTLIST_FAILURE_MIN", 3)
    if summary["failed"] >= minimum and summary["failed"] / summary["attempted"] >= ratio:
        return 1
    return 0


def _report_failures(snapshots) -> None:
    summary = _failure_summary(snapshots)
    print("[summary] " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path or not summary["failed"]:
        return
    error_types = ", ".join(f"{key}={count}" for key, count in sorted(summary["errorTypes"].items()))
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write(
            f"### 采集失败 {summary['failed']}/{summary['attempted']}\n\n"
            f"- 错误类型：{error_types}\n"
            f"- 渠道：{', '.join(summary['failedChannels'])}\n\n"
        )


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()
    snapshots = run(
        args.channels,
        args.latest_path,
        due_only=args.due,
        data_root=args.data_root,
        surface=args.surface,
    )
    _report_failures(snapshots)
    return _exit_code_for_snapshots(snapshots)


if __name__ == "__main__":
    raise SystemExit(main())
