import json
import unittest
from pathlib import Path

from src.hotlist.catalog import apply_catalog_delta, build_catalog, build_catalog_delta
from src.hotlist.registry import CHANNEL_ORDER


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "config/channels/base.v1.json"
CURRENT = ROOT / "config/channels/current.json"


class ChannelCatalogTests(unittest.TestCase):
    def test_current_catalog_matches_runtime_registry(self):
        stored = json.loads(CURRENT.read_text(encoding="utf-8"))
        generated = build_catalog()

        self.assertEqual(stored, generated)
        self.assertEqual([item["channelId"] for item in stored["channels"]], list(CHANNEL_ORDER))
        for channel in stored["channels"]:
            self.assertTrue(channel["name"])
            self.assertTrue(channel["homepage"])
            self.assertTrue(channel["surfaces"])
            self.assertTrue(channel["collector"]["module"])
            self.assertTrue(channel["collector"]["endpoints"])
            self.assertIn("requirements", channel)

    def test_base_snapshot_is_immutable_version_one_shape(self):
        baseline = json.loads(BASE.read_text(encoding="utf-8"))

        self.assertEqual(baseline["schemaVersion"], 1)
        self.assertEqual(baseline["catalogVersion"], "1.0.0")
        self.assertEqual(len(baseline["channels"]), 39)

    def test_delta_round_trip_reconstructs_target_catalog(self):
        base = {
            "schemaVersion": 1,
            "catalogVersion": "1.0.0",
            "channels": [{"channelId": "a", "name": "A"}],
        }
        target = {
            "schemaVersion": 1,
            "catalogVersion": "1.1.0",
            "channels": [{"channelId": "a", "name": "A2"}, {"channelId": "b", "name": "B"}],
        }

        delta = build_catalog_delta(base, target, "add-b-and-update-a")

        self.assertEqual(apply_catalog_delta(base, delta), target)
        self.assertEqual([item["op"] for item in delta["operations"]], ["replace", "add"])


if __name__ == "__main__":
    unittest.main()
