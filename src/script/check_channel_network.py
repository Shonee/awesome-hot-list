"""Check newly added channel endpoints from the GitHub Actions network."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.http_utils import get


ENDPOINTS = {
    "cnblogs": "https://www.cnblogs.com/aggsite/topdigged24h",
    "linuxdo": "https://linux.do/top.json?period=weekly",
    "nodeseek": "https://www.nodeseek.com/?tab=hot",
    "pojie52": "https://www.52pojie.cn/forum.php?mod=guide&view=hot",
    "qqnews": "https://news.qq.com/",
    "tieba": "https://tieba.baidu.com/hottopic/browse/topicList",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="验证新增渠道在 GitHub Actions 网络中的可达性")
    parser.add_argument("channels", nargs="*", choices=tuple(ENDPOINTS))
    args = parser.parse_args()
    channels = args.channels or list(ENDPOINTS)
    failed = 0
    for channel_id in channels:
        url = ENDPOINTS[channel_id]
        try:
            body = get(url, res_type="text", timeout=12, retries=1)
            size = len(body)
            if size < 100:
                raise RuntimeError(f"response too small: {size} bytes")
            print(f"[ok]   {channel_id}: {size} bytes")
        except Exception as exc:  # noqa: BLE001 - report every endpoint independently
            failed += 1
            print(f"[fail] {channel_id}: {exc}")
    if failed:
        print(f"{failed} endpoint(s) unavailable from the runner network", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
