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
