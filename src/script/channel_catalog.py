#!/usr/bin/env python3
"""Validate, export, and incrementally update the channel catalog."""

import argparse
import json
import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.hotlist.catalog import (
    CATALOG_UPDATED_AT,
    CATALOG_VERSION,
    build_catalog,
    build_catalog_delta,
    replay_catalog_deltas,
)
from src.utils.file_utils import write_json


DEFAULT_BASE = os.path.join(ROOT, "config", "channels", "base.v1.json")
DEFAULT_CURRENT = os.path.join(ROOT, "config", "channels", "current.json")
DEFAULT_CHANGES = os.path.join(ROOT, "config", "channels", "changes")


def _read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _change_files(changes_dir: str) -> list[str]:
    if not os.path.isdir(changes_dir):
        return []
    return [
        os.path.join(changes_dir, name)
        for name in sorted(os.listdir(changes_dir))
        if name.endswith(".json")
    ]


def check(
    current_path: str = DEFAULT_CURRENT,
    base_path: str = DEFAULT_BASE,
    changes_dir: str = DEFAULT_CHANGES,
) -> None:
    current = _read(current_path)
    baseline = _read(base_path)
    # The code constants are the source of truth: deriving them from current.json
    # would let a hand-edited version field validate its own stale content.
    expected = build_catalog()
    if current != expected:
        raise SystemExit(
            "channel catalog is stale; run channel_catalog.py sync --version "
            f"{CATALOG_VERSION} --updated-at {CATALOG_UPDATED_AT} --change-id <id>"
        )
    if baseline.get("schemaVersion") != 1 or baseline.get("catalogVersion") != "1.0.0":
        raise SystemExit("channel catalog baseline must remain schema 1 / catalog 1.0.0")
    try:
        replayed = replay_catalog_deltas(baseline, [_read(path) for path in _change_files(changes_dir)])
    except ValueError as exc:
        raise SystemExit(f"channel catalog history does not replay: {exc}") from exc
    if replayed != current:
        raise SystemExit(
            "channel catalog history does not replay to current.json; "
            "a published change file must never be edited"
        )


def sync(current_path: str, changes_dir: str, version: str, updated_at: str, change_id: str) -> None:
    previous = _read(current_path)
    target = build_catalog(version, updated_at)
    delta = build_catalog_delta(previous, target, change_id)
    if not delta["operations"] and previous == target:
        raise SystemExit("channel catalog already matches the requested version")
    os.makedirs(changes_dir, exist_ok=True)
    write_json(delta, os.path.join(changes_dir, f"{change_id}.json"), atomic=True)
    write_json(target, current_path, atomic=True)


def rebuild(base_path: str, changes_dir: str, output_path: str) -> None:
    catalog = replay_catalog_deltas(
        _read(base_path), [_read(path) for path in _change_files(changes_dir)]
    )
    write_json(catalog, output_path, atomic=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the versioned channel catalog")
    commands = parser.add_subparsers(dest="command", required=True)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--base", default=DEFAULT_BASE)
    check_parser.add_argument("--current", default=DEFAULT_CURRENT)
    check_parser.add_argument("--changes-dir", default=DEFAULT_CHANGES)
    export_parser = commands.add_parser("export")
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument("--version", default=CATALOG_VERSION)
    export_parser.add_argument("--updated-at", default=CATALOG_UPDATED_AT)
    sync_parser = commands.add_parser("sync")
    sync_parser.add_argument("--current", default=DEFAULT_CURRENT)
    sync_parser.add_argument("--changes-dir", default=DEFAULT_CHANGES)
    sync_parser.add_argument("--version", required=True)
    sync_parser.add_argument("--updated-at", required=True)
    sync_parser.add_argument("--change-id", required=True)
    rebuild_parser = commands.add_parser("rebuild")
    rebuild_parser.add_argument("--base", default=DEFAULT_BASE)
    rebuild_parser.add_argument("--changes-dir", default=DEFAULT_CHANGES)
    rebuild_parser.add_argument("--output", default=DEFAULT_CURRENT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "check":
        check(args.current, args.base, args.changes_dir)
    elif args.command == "export":
        write_json(build_catalog(args.version, args.updated_at), args.output, atomic=True)
    elif args.command == "sync":
        sync(args.current, args.changes_dir, args.version, args.updated_at, args.change_id)
    elif args.command == "rebuild":
        rebuild(args.base, args.changes_dir, args.output)


if __name__ == "__main__":
    main()
