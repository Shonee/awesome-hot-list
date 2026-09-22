import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.hotlist.catalog import (
    apply_catalog_delta,
    build_catalog,
    build_catalog_delta,
    replay_catalog_deltas,
)
from src.hotlist.registry import CHANNEL_ORDER
from src.script.channel_catalog import check


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "config/channels/base.v1.json"
CURRENT = ROOT / "config/channels/current.json"
CHANGES = ROOT / "config/channels/changes"


def _published_deltas() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(CHANGES.glob("*.json"))]


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

    def test_published_history_replays_from_any_input_order(self):
        baseline = json.loads(BASE.read_text(encoding="utf-8"))
        stored = json.loads(CURRENT.read_text(encoding="utf-8"))
        deltas = _published_deltas()

        self.assertEqual(len(deltas), len({delta["changeId"] for delta in deltas}))
        self.assertEqual(replay_catalog_deltas(baseline, deltas), stored)
        self.assertEqual(replay_catalog_deltas(baseline, list(reversed(deltas))), stored)

    def test_file_name_order_is_not_a_valid_replay_order(self):
        base = {
            "schemaVersion": 1,
            "catalogVersion": "1.0.0",
            "channels": [{"channelId": "a", "name": "A"}],
        }
        step_one = build_catalog_delta(base, {**base, "catalogVersion": "1.0.1"}, "zzz-disable-a.json")
        step_two = build_catalog_delta(
            {**base, "catalogVersion": "1.0.1"},
            {**base, "catalogVersion": "1.1.0", "channels": [{"channelId": "a", "name": "A2"}]},
            "aaa-update-a.json",
        )

        # Reading the directory in file-name order would apply the later change first.
        with self.assertRaises(ValueError):
            catalog = base
            for delta in (step_two, step_one):
                catalog = apply_catalog_delta(catalog, delta)

        self.assertEqual(
            replay_catalog_deltas(base, [step_two, step_one])["catalogVersion"], "1.1.0"
        )

    def test_replay_rejects_forked_or_unreachable_history(self):
        baseline = json.loads(BASE.read_text(encoding="utf-8"))
        deltas = _published_deltas()
        fork = json.loads(json.dumps(deltas[0]))
        fork["changeId"] = "forked-first-delta"
        fork["toVersion"] = "1.0.0-fork"

        with self.assertRaisesRegex(ValueError, "more than one next delta"):
            replay_catalog_deltas(baseline, deltas + [fork])
        with self.assertRaisesRegex(ValueError, "no delta starts here"):
            replay_catalog_deltas(baseline, deltas[1:])

    def test_check_requires_history_and_version_constants_to_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "channels"
            shutil.copytree(ROOT / "config/channels", config)
            # A published change file is immutable history; editing it must not replay.
            delta_path = sorted((config / "changes").glob("*add-jandan*.json"))[0]
            delta = json.loads(delta_path.read_text(encoding="utf-8"))
            delta["operations"] = delta["operations"][:3]
            delta_path.write_text(json.dumps(delta, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(SystemExit, "does not replay"):
                check(str(config / "current.json"), str(config / "base.v1.json"), str(config / "changes"))

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "channels"
            shutil.copytree(ROOT / "config/channels", config)
            # current.json is a derived file: its version fields cannot be the
            # baseline for validating itself.
            stored = json.loads((config / "current.json").read_text(encoding="utf-8"))
            stored["catalogVersion"] = "9.9.9"
            (config / "current.json").write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(SystemExit, "is stale"):
                check(str(config / "current.json"), str(config / "base.v1.json"), str(config / "changes"))

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
