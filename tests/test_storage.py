import os
import tempfile
import unittest

from src.utils.file_utils import archive_path, read_csv, write_csv, write_json


class ArchivePathTests(unittest.TestCase):
    def test_compact_site_json_preserves_values_without_whitespace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "site.json")
            write_json({"title": "热榜", "items": [1, 2]}, path, indent=None, atomic=True)
            with open(path, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), '{"title":"热榜","items":[1,2]}')

    def test_archive_path_is_partitioned_by_date_and_format(self):
        self.assertEqual(
            archive_path("douyin", "csv", "2026-09-01"),
            "archived/douyin/2026/09/csv/2026-09-01.csv",
        )

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ValueError):
            archive_path("douyin", "xml", "2026-09-01")

    def test_invalid_date_is_rejected(self):
        with self.assertRaises(ValueError):
            archive_path("douyin", "csv", "2026-13-01")

    def test_append_evolves_existing_csv_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "data.csv")
            write_csv([{"title": "first"}], path)
            write_csv([{"title": "second", "new_field": "kept"}], path)

            self.assertEqual(
                read_csv(path),
                [
                    {"title": "first", "new_field": ""},
                    {"title": "second", "new_field": "kept"},
                ],
            )

    def test_atomic_append_keeps_existing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "data.csv")
            write_csv([{"title": "first"}], path, atomic=True)
            write_csv([{"title": "second"}], path, atomic=True)

            self.assertEqual([row["title"] for row in read_csv(path)], ["first", "second"])

    def test_unreadable_existing_csv_is_never_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "data.csv")
            with open(path, "wb") as stream:
                stream.write(b"\xff\xfe existing archive\n")

            with self.assertRaises(OSError):
                write_csv([{"title": "today"}], path, mode="append", atomic=True)

            with open(path, "rb") as stream:
                self.assertEqual(stream.read(), b"\xff\xfe existing archive\n")


if __name__ == "__main__":
    unittest.main()
