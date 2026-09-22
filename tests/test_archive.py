import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from src.script.archive import clean, prepare, verify


class WeeklyArchiveTests(unittest.TestCase):
    def test_prepare_keeps_seven_days_and_packages_older_csv_and_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_csv = root / "archived" / "demo" / "2026" / "08" / "csv" / "2026-08-31.csv"
            kept_csv = root / "archived" / "demo" / "2026" / "09" / "csv" / "2026-09-01.csv"
            old_report = root / "site" / "data" / "reports" / "2026-08-31.json"
            kept_report = root / "site" / "data" / "reports" / "2026-09-01.json"
            for path in (old_csv, kept_csv, old_report, kept_report):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(path.name, encoding="utf-8")
            index_path = root / "site" / "data" / "reports" / "index.json"
            index_path.write_text(
                json.dumps({
                    "schemaVersion": 1,
                    "generatedAt": "2026-09-07 02:00:00",
                    "dates": ["2026-09-01", "2026-08-31"],
                    "reports": [
                        {"date": "2026-09-01", "path": "./data/reports/2026-09-01.json"},
                        {"date": "2026-08-31", "path": "./data/reports/2026-08-31.json"},
                    ],
                }),
                encoding="utf-8",
            )

            output = root / ".archive-work"
            result = prepare(root, output, dt.date(2026, 9, 7), retention_days=7)

            self.assertTrue(result["hasFiles"])
            self.assertEqual(
                {entry["path"] for entry in result["files"]},
                {"archived/demo/2026/08/csv/2026-08-31.csv", "site/data/reports/2026-08-31.json"},
            )
            self.assertEqual(verify(root, output)["archiveId"], result["archiveId"])
            self.assertEqual(clean(root, output), 2)
            self.assertFalse(old_csv.exists())
            self.assertFalse(old_report.exists())
            self.assertTrue(kept_csv.exists())
            self.assertTrue(kept_report.exists())
            refreshed_index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed_index["dates"], ["2026-09-01"])

    def test_compaction_failure_is_recovered_by_the_next_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stranded = root / "archived" / "demo" / "2026" / "09" / "csv" / "2026-09-08.csv"
            stranded.parent.mkdir(parents=True)
            stranded.write_text("row", encoding="utf-8")

            first = prepare(root, root / ".archive-work", dt.date(2026, 9, 21), retention_days=7)
            self.assertEqual(
                [entry["path"] for entry in first["files"]],
                ["archived/demo/2026/09/csv/2026-09-08.csv"],
            )

            # The release is published before the branch is compacted, so a failed
            # compaction leaves the files behind; the next weekly run must pick them
            # up again instead of stranding them past the retention window.
            second = prepare(root, root / ".archive-work-next", dt.date(2026, 9, 28), retention_days=7)

            self.assertEqual(
                [entry["path"] for entry in second["files"]],
                [entry["path"] for entry in first["files"]],
            )
            # Recovery rides a new tag, so the recovered days land in two releases.
            self.assertNotEqual(second["archiveId"], first["archiveId"])

    def test_empty_selection_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = prepare(root, root / ".archive-work", dt.date(2026, 9, 7), retention_days=7)
            self.assertFalse(result["hasFiles"])
            self.assertEqual(verify(root, root / ".archive-work")["hasFiles"], False)
            self.assertEqual(clean(root, root / ".archive-work"), 0)

    def test_manifest_distinguishes_source_and_data_commits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_csv = root / "archived" / "demo" / "2026" / "08" / "csv" / "2026-08-31.csv"
            old_csv.parent.mkdir(parents=True, exist_ok=True)
            old_csv.write_text("old", encoding="utf-8")

            result = prepare(
                root,
                root / ".archive-work",
                dt.date(2026, 9, 7),
                retention_days=7,
                source_commit="source-sha",
            )

            self.assertEqual(result["sourceCommit"], "source-sha")
            self.assertEqual(result["dataCommit"], "unknown")

    def test_legacy_mode_includes_old_formats_but_keeps_channel_readme(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "archived" / "demo" / "data.json"
            recent_legacy = root / "archived" / "demo" / "2026" / "09" / "json" / "2026-09-04.json"
            readme = root / "archived" / "demo" / "README.md"
            current = root / "archived" / "demo" / "2026" / "09" / "csv" / "2026-09-05.csv"
            for path in (legacy, recent_legacy, readme, current):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(path.name, encoding="utf-8")

            result = prepare(
                root,
                root / ".archive-work",
                dt.date(2026, 9, 5),
                retention_days=7,
                include_legacy=True,
            )
            paths = {entry["path"] for entry in result["files"]}
            self.assertIn("archived/demo/data.json", paths)
            self.assertIn("archived/demo/2026/09/json/2026-09-04.json", paths)
            self.assertEqual(result["archiveId"], "hotlist-archive-legacy-cleanup-2026-09-05")
            self.assertNotIn("archived/demo/README.md", paths)
            self.assertNotIn("archived/demo/2026/09/csv/2026-09-05.csv", paths)
            verify(root, root / ".archive-work")


if __name__ == "__main__":
    unittest.main()
