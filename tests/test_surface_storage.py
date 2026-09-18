import json
import tempfile
import unittest
from pathlib import Path

from src.hotlist.models import ChannelSnapshot, HotItem, Ranking
from src.hotlist.registry import CHANNEL_ORDER, CHANNEL_SURFACES, ChannelDefinition, get_channel
from src.hotlist.runner import collect_channels, migrate_surface_files, surface_data_path, write_surface_snapshots


class SurfaceRegistryTests(unittest.TestCase):
    def test_every_registered_channel_has_an_explicit_surface_contract(self):
        self.assertEqual(set(CHANNEL_SURFACES), set(CHANNEL_ORDER))

    def test_mixed_and_non_hotlist_channels_declare_surfaces(self):
        self.assertEqual(get_channel("sina").surfaces, ("hotlist", "live"))
        self.assertEqual(get_channel("cls").surfaces, ("hotlist", "live"))
        self.assertEqual(get_channel("wallstreetcn").surfaces, ("live",))
        self.assertEqual(get_channel("readhub").surfaces, ("digest",))
        self.assertEqual(get_channel("cctv").surfaces, ("authority",))
        self.assertEqual(get_channel("mfa").surfaces, ("authority",))
        self.assertEqual(get_channel("yicai").surfaces, ("hotlist", "live"))

    def test_collector_cannot_return_an_undeclared_surface(self):
        def collect_live_only():
            return ChannelSnapshot(
                "demo",
                "Demo",
                "https://example.com",
                "2026-09-17 12:00:00",
                [Ranking("live", "Live", [HotItem(1, "item", "https://example.com/1")], surface="live")],
            )

        definitions = {
            "demo": ChannelDefinition(
                "demo", "Demo", 1, "D", "#000000", collect_live_only, surfaces=("hotlist",)
            )
        }

        snapshots = collect_channels(["demo"], definitions=definitions)

        self.assertEqual(snapshots[0].status, "error")
        self.assertIn("undeclared ranking surface", snapshots[0].error)


class SurfaceStorageTests(unittest.TestCase):
    def test_surface_paths_keep_hotlist_compatibility(self):
        root = Path("site/data/latest.json")

        self.assertEqual(surface_data_path(root, "hotlist"), root)
        self.assertEqual(surface_data_path(root, "live"), Path("site/data/live.json"))
        self.assertEqual(surface_data_path(root, "digest"), Path("site/data/digest.json"))
        self.assertEqual(surface_data_path(root, "authority"), Path("site/data/authority.json"))

    def test_snapshots_are_written_to_surface_specific_files(self):
        snapshot = ChannelSnapshot(
            "sina",
            "新浪",
            "https://news.sina.com.cn/",
            "2026-09-17 12:00:00",
            [
                Ranking("news", "新闻热榜", [HotItem(1, "热榜", "https://example.com/hot")]),
                Ranking("live", "7x24", [HotItem(1, "快讯", "https://example.com/live")], surface="live"),
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            latest = Path(directory) / "site/data/latest.json"
            outputs = write_surface_snapshots([snapshot], latest)

            hotlist = json.loads(latest.read_text(encoding="utf-8"))
            live = json.loads(surface_data_path(latest, "live").read_text(encoding="utf-8"))

        self.assertEqual(set(outputs), {"hotlist", "live"})
        self.assertEqual([item["surface"] for item in hotlist["channels"][0]["rankings"]], ["hotlist"])
        self.assertEqual([item["surface"] for item in live["channels"][0]["rankings"]], ["live"])

    def test_legacy_combined_snapshot_is_migrated_without_overwriting_newer_surface_file(self):
        with tempfile.TemporaryDirectory() as directory:
            latest = Path(directory) / "site/data/latest.json"
            latest.parent.mkdir(parents=True)
            latest.write_text(json.dumps({"channels": [{
                "channelId": "sina",
                "channelName": "新浪",
                "status": "ok",
                "rankings": [
                    {"id": "news", "name": "热榜", "surface": "hotlist", "items": [{"title": "热榜"}]},
                    {"id": "live", "name": "7x24", "surface": "live", "items": [{"title": "旧快讯"}]},
                ],
            }]}), encoding="utf-8")
            live_path = surface_data_path(latest, "live")
            live_path.write_text(json.dumps({"channels": [{
                "channelId": "sina",
                "channelName": "新浪",
                "status": "ok",
                "rankings": [{"id": "live", "name": "7x24", "surface": "live", "items": [{"title": "新快讯"}]}],
            }]}), encoding="utf-8")

            migrate_surface_files(latest)

            hotlist = json.loads(latest.read_text(encoding="utf-8"))
            live = json.loads(live_path.read_text(encoding="utf-8"))

        self.assertEqual([item["surface"] for item in hotlist["channels"][0]["rankings"]], ["hotlist"])
        self.assertEqual(live["channels"][0]["rankings"][0]["items"][0]["title"], "新快讯")


if __name__ == "__main__":
    unittest.main()
