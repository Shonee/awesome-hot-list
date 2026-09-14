import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.hotlist.channels import rss
from src.hotlist.channels.rss import DEFAULT_FEEDS
from src.hotlist.models import ChannelSnapshot
from src.hotlist.registry import CHANNEL_ORDER
from src.hotlist.runner import merge_latest_snapshot


class RssSourceOwnershipTests(unittest.TestCase):
    def test_linuxdo_official_rss_is_in_aggregate_card_only(self):
        self.assertIn(("Linux.do", "https://linux.do/top.rss?period=weekly"), DEFAULT_FEEDS)
        self.assertNotIn("linuxdo", CHANNEL_ORDER)

    def test_ithome_official_rss_is_in_aggregate_card_only(self):
        self.assertIn(("IT之家", "https://www.ithome.com/rss/"), DEFAULT_FEEDS)
        self.assertNotIn("ithome", CHANNEL_ORDER)

    def test_retired_rss_backed_snapshots_are_removed_during_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(
                json.dumps({"channels": [
                    {"channelId": "linuxdo", "status": "stale"},
                    {"channelId": "ithome", "status": "ok"},
                ]}),
                encoding="utf-8",
            )
            current = ChannelSnapshot.unavailable(
                "rss", "RSS", "", "2026-09-14 09:00:00", "error", "feed unavailable"
            )

            payload = merge_latest_snapshot([current], str(path))

        self.assertNotIn("linuxdo", [item["channelId"] for item in payload["channels"]])
        self.assertNotIn("ithome", [item["channelId"] for item in payload["channels"]])

    def test_all_rss_failures_are_reported_as_collection_errors(self):
        with (
            patch.dict(os.environ, {"HOTLIST_RSS_FEEDS": "测试源|https://example.com/feed"}),
            patch("src.hotlist.channels.rss.get", side_effect=RuntimeError("network down")),
        ):
            with self.assertRaisesRegex(RuntimeError, "no RSS feed returned usable items"):
                rss.collect()

    def test_partial_rss_failures_are_exposed_as_snapshot_warnings(self):
        xml = """<?xml version="1.0"?><rss><channel><title>成功源</title><item>
        <title>示例文章</title><link>https://example.com/article</link>
        </item></channel></rss>"""
        with (
            patch.dict(
                os.environ,
                {"HOTLIST_RSS_FEEDS": "成功源|https://ok.example/feed,失败源|https://bad.example/feed"},
            ),
            patch("src.hotlist.channels.rss.get", side_effect=[xml, RuntimeError("network down")]),
        ):
            result = rss.collect()

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.warnings, ["失败源"])
        self.assertEqual(result.to_dict()["warnings"], ["失败源"])


if __name__ == "__main__":
    unittest.main()
