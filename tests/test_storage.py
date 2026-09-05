import os
import tempfile
import unittest

from src.utils.file_utils import archive_path, read_csv, write_csv


class ArchivePathTests(unittest.TestCase):
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

    def test_append_keeps_existing_csv_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "data.csv")
            write_csv([{"title": "first"}], path)
            write_csv([{"title": "second", "new_field": "ignored"}], path)

            self.assertEqual(
                read_csv(path),
                [{"title": "first"}, {"title": "second"}],
            )


if __name__ == "__main__":
    unittest.main()
