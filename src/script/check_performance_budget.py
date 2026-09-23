#!/usr/bin/env python3
"""Fail fast when static data regresses beyond the agreed page budgets."""

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.hotlist.registry import CHANNELS


SURFACE_FILES = {
    "hotlist": "latest.json",
    "live": "live.json",
    "digest": "digest.json",
    "authority": "authority.json",
}
DEFAULT_MAX_HOTLIST_GZIP_BYTES = 300 * 1024


def _declared_channels() -> dict:
    """Per surface, the channels the registry expects to see published."""
    return {
        surface: [
            channel.channel_id
            for channel in CHANNELS.values()
            if surface in channel.surfaces and channel.enabled_by_default
        ]
        for surface in SURFACE_FILES
    }


def check_data_budgets(data_root, max_hotlist_gzip_bytes: int = DEFAULT_MAX_HOTLIST_GZIP_BYTES) -> dict:
    data_dir = Path(data_root) / "site/data"
    sizes = {}
    declared = _declared_channels()
    published = {}
    for expected_surface, filename in SURFACE_FILES.items():
        path = data_dir / filename
        if not path.is_file():
            raise ValueError(f"missing surface data file: {filename}")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {filename}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("channels"), list):
            raise ValueError(f"invalid surface payload shape: {filename}")
        for channel in payload["channels"]:
            for ranking in channel.get("rankings", []):
                actual_surface = str(ranking.get("surface") or "hotlist").strip().lower()
                if actual_surface != expected_surface:
                    raise ValueError(f"{filename} contains {actual_surface} ranking")
        published[expected_surface] = {
            "channels": len(payload["channels"]),
            "items": sum(
                len(ranking.get("items") or [])
                for channel in payload["channels"]
                for ranking in channel.get("rankings") or []
            ),
        }
        sizes[expected_surface] = {
            "rawBytes": len(raw),
            "gzipBytes": len(gzip.compress(raw, compresslevel=9)),
        }
    # 采集失败时上游会保留上一轮榜单，所以"零条目"不是一次抖动，而是这个内容面
    # 从来没有成功发布过；72 字节的空文件同样不该通过预算门禁。
    for surface, stats in published.items():
        filename = SURFACE_FILES[surface]
        if not declared[surface]:
            continue
        if not stats["channels"]:
            raise ValueError(
                f"{filename} is empty although {len(declared[surface])} channels declare the {surface} surface"
            )
        if not stats["items"]:
            raise ValueError(f"{filename} has {stats['channels']} channels but no ranked items")
    hotlist_gzip = sizes["hotlist"]["gzipBytes"]
    if hotlist_gzip > max_hotlist_gzip_bytes:
        raise ValueError(
            f"latest.json gzip size {hotlist_gzip} exceeds budget {max_hotlist_gzip_bytes}"
        )
    return {
        "surfaceFiles": len(SURFACE_FILES),
        "hotlistGzipBytes": hotlist_gzip,
        "maxHotlistGzipBytes": max_hotlist_gzip_bytes,
        "published": published,
        "sizes": sizes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check static hot-list performance budgets")
    parser.add_argument("--data-root", default=".")
    parser.add_argument("--max-hotlist-gzip-bytes", type=int, default=DEFAULT_MAX_HOTLIST_GZIP_BYTES)
    args = parser.parse_args()
    result = check_data_budgets(args.data_root, args.max_hotlist_gzip_bytes)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
