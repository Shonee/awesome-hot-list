import unittest

from src.hotlist.models import ChannelSnapshot, HotItem, Ranking
from src.script.check_channel_network import PROBES, SKIPPED_SOURCES, count_snapshot_items, require_items


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

    def test_bing_and_new_content_sources_have_network_probes(self):
        self.assertNotIn("bing", SKIPPED_SOURCES)
        self.assertFalse(PROBES["bing"].required)
        for probe_id in ("sina-live", "cls-live", "wallstreetcn", "readhub", "cctv", "mfa"):
            with self.subTest(probe_id=probe_id):
                self.assertIn(probe_id, PROBES)

    def test_new_official_rankings_and_yicai_live_have_probes(self):
        for channel_id in ("autohome", "gamersky", "ithome", "yicai", "yicai-live"):
            with self.subTest(channel_id=channel_id):
                self.assertIn(channel_id, PROBES)

    def test_rss_probe_is_retired(self):
        self.assertNotIn("linuxdo", PROBES)

    def test_kuaishou_chain_is_required_but_diagnostic_sources_are_optional(self):
        self.assertTrue(PROBES["kuaishou"].required)
        self.assertFalse(PROBES["kuaishou-official"].required)
        self.assertFalse(PROBES["dailyhot-kuaishou"].required)


if __name__ == "__main__":
    unittest.main()
