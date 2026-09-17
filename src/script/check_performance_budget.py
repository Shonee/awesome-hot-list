#!/usr/bin/env python3
"""Fail fast when static data regresses beyond the agreed page budgets."""

import argparse
import gzip
import json
from pathlib import Path


SURFACE_FILES = {
    "hotlist": "latest.json",
    "live": "live.json",
    "digest": "digest.json",
    "authority": "authority.json",
}
DEFAULT_MAX_HOTLIST_GZIP_BYTES = 300 * 1024


def check_data_budgets(data_root, max_hotlist_gzip_bytes: int = DEFAULT_MAX_HOTLIST_GZIP_BYTES) -> dict:
    data_dir = Path(data_root) / "site/data"
    sizes = {}
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
        sizes[expected_surface] = {
            "rawBytes": len(raw),
            "gzipBytes": len(gzip.compress(raw, compresslevel=9)),
        }
    hotlist_gzip = sizes["hotlist"]["gzipBytes"]
    if hotlist_gzip > max_hotlist_gzip_bytes:
        raise ValueError(
            f"latest.json gzip size {hotlist_gzip} exceeds budget {max_hotlist_gzip_bytes}"
        )
    return {
        "surfaceFiles": len(SURFACE_FILES),
        "hotlistGzipBytes": hotlist_gzip,
        "maxHotlistGzipBytes": max_hotlist_gzip_bytes,
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
