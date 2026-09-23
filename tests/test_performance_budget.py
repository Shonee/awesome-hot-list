import json
import tempfile
import unittest
from pathlib import Path

from src.script.check_performance_budget import check_data_budgets


class PerformanceBudgetTests(unittest.TestCase):
    def test_accepts_split_surface_payloads_under_the_hotlist_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "site/data"
            data.mkdir(parents=True)
            for surface, filename in (
                ("hotlist", "latest.json"),
                ("live", "live.json"),
                ("digest", "digest.json"),
                ("authority", "authority.json"),
            ):
                payload = {"channels": [{"channelId": surface, "rankings": [{
                    "id": surface,
                    "name": surface,
                    "surface": surface,
                    "items": [{"title": "item"}],
                }]}]}
                (data / filename).write_text(json.dumps(payload), encoding="utf-8")

            result = check_data_budgets(root, max_hotlist_gzip_bytes=1024)

        self.assertLess(result["hotlistGzipBytes"], 1024)
        self.assertEqual(result["surfaceFiles"], 4)
        self.assertEqual(result["published"]["live"], {"channels": 1, "items": 1})

    def test_rejects_an_empty_surface_the_registry_still_declares(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "site/data"
            data.mkdir(parents=True)
            for filename in ("latest.json", "live.json", "digest.json", "authority.json"):
                (data / filename).write_text('{"channels": []}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "latest.json is empty"):
                check_data_budgets(root)

    def test_rejects_a_surface_without_ranked_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "site/data"
            data.mkdir(parents=True)
            empty = {"channels": [{"channelId": "x", "rankings": [
                {"id": "x", "name": "x", "surface": "hotlist", "items": []},
            ]}]}
            for surface, filename in (
                ("hotlist", "latest.json"),
                ("live", "live.json"),
                ("digest", "digest.json"),
                ("authority", "authority.json"),
            ):
                payload = json.loads(json.dumps(empty))
                payload["channels"][0]["rankings"][0]["surface"] = surface
                (data / filename).write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "latest.json has 1 channels but no ranked items"):
                check_data_budgets(root)

    def test_rejects_a_ranking_stored_in_the_wrong_surface_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "site/data"
            data.mkdir(parents=True)
            for filename in ("latest.json", "live.json", "digest.json", "authority.json"):
                (data / filename).write_text('{"channels": []}', encoding="utf-8")
            (data / "live.json").write_text(json.dumps({"channels": [{
                "channelId": "bad",
                "rankings": [{"id": "bad", "name": "bad", "surface": "hotlist", "items": []}],
            }]}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "live.json contains hotlist"):
                check_data_budgets(root)


if __name__ == "__main__":
    unittest.main()
