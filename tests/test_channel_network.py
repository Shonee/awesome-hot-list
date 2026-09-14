import unittest

from src.hotlist.models import ChannelSnapshot, HotItem, Ranking
from src.script.check_channel_network import SKIPPED_SOURCES, count_snapshot_items, require_items


class ChannelNetworkValidationTests(unittest.TestCase):
    def test_snapshot_validation_counts_real_items(self):
        snapshot = ChannelSnapshot(
            "demo",
            "Demo",
            "https://example.com",
            "2026-09-14 00:00:00",
            rankings=[Ranking("hot", "Hot", [
                HotItem(1, "One", "https://example.com/1"),
                HotItem(2, "Two", "https://example.com/2"),
            ])],
        )

        self.assertEqual(count_snapshot_items(snapshot), 2)

    def test_validator_rejects_structurally_empty_success(self):
        with self.assertRaisesRegex(RuntimeError, "only 0 valid item"):
            require_items("demo", 0, minimum=5)

    def test_bing_is_explicitly_skipped_without_non_rss_source(self):
        self.assertIn("bing", SKIPPED_SOURCES)
        self.assertIn("non-RSS", SKIPPED_SOURCES["bing"])


if __name__ == "__main__":
    unittest.main()
