import unittest

from src.script.render import _latest_from_rows


class LatestFallbackTests(unittest.TestCase):
    def test_latest_snapshot_uses_newest_slice_per_ranking(self):
        rows = {
            "douyin": [
                {
                    "index": 1,
                    "title": "旧热点",
                    "url": "https://example.com/old",
                    "type": "热搜",
                    "datetime": "2026-09-04 09:00:00",
                },
                {
                    "index": 1,
                    "title": "新热点",
                    "url": "https://example.com/new",
                    "type": "热搜",
                    "datetime": "2026-09-04 12:00:00",
                },
            ]
        }

        snapshots = _latest_from_rows("2026-09-04", rows)

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].fetched_at, "2026-09-04 12:00:00")
        self.assertEqual(snapshots[0].rankings[0].items[0].title, "新热点")


if __name__ == "__main__":
    unittest.main()
