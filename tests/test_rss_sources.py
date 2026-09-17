import unittest
import json
import tempfile
from pathlib import Path

from src.hotlist.channels.rss import DEFAULT_FEEDS
from src.hotlist.models import ChannelSnapshot
from src.hotlist.registry import CHANNEL_ORDER, get_channel
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
                    {"channelId": "rss", "status": "ok"},
                ]}),
                encoding="utf-8",
            )
            current = ChannelSnapshot.unavailable(
                "rss", "RSS", "", "2026-09-14 09:00:00", "error", "feed unavailable"
            )

            payload = merge_latest_snapshot([current], str(path))

        self.assertNotIn("linuxdo", [item["channelId"] for item in payload["channels"]])
        self.assertNotIn("ithome", [item["channelId"] for item in payload["channels"]])
        self.assertNotIn("rss", [item["channelId"] for item in payload["channels"]])

    def test_rss_is_retired_from_registration_and_default_collection(self):
        self.assertNotIn("rss", CHANNEL_ORDER)
        with self.assertRaisesRegex(ValueError, "unknown channel: rss"):
            get_channel("rss")


if __name__ == "__main__":
    unittest.main()
