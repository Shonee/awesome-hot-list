import unittest
import tempfile
from pathlib import Path

from src.script.render import _add_day_comparison, _available_report_dates, _latest_from_rows


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


class ReportNavigationTests(unittest.TestCase):
    def test_available_report_dates_returns_latest_seven_dated_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for day in range(1, 10):
                (root / f"2026-09-{day:02d}.json").write_text("{}", encoding="utf-8")
            (root / "today.json").write_text("{}", encoding="utf-8")
            (root / "not-a-date.json").write_text("{}", encoding="utf-8")
            (root / "2026-99-99.json").write_text("{}", encoding="utf-8")

            dates = _available_report_dates(str(root))

        self.assertEqual(
            dates,
            [
                "2026-09-09",
                "2026-09-08",
                "2026-09-07",
                "2026-09-06",
                "2026-09-05",
                "2026-09-04",
                "2026-09-03",
            ],
        )

    def test_day_comparison_marks_new_continued_and_dropped_topics(self):
        today = {
            "date": "2026-09-06",
            "topTopics": [
                {"title": "延续热点", "url": "https://example.com/continued", "hits": []},
                {"title": "今日新增", "url": "https://example.com/new", "hits": []},
            ],
        }
        previous = {
            "date": "2026-09-05",
            "topTopics": [
                {"title": "延续热点", "url": "https://example.com/continued", "hits": []},
                {"title": "昨日热点", "url": "https://example.com/dropped", "hits": []},
            ],
        }

        enriched = _add_day_comparison(today, previous)

        self.assertIs(enriched, today)
        self.assertEqual(enriched["dayComparison"]["baselineDate"], "2026-09-05")
        self.assertEqual(
            enriched["dayComparison"]["counts"],
            {"new": 1, "continued": 1, "rising": 0, "falling": 0, "dropped": 1},
        )
        self.assertEqual([item["title"] for item in enriched["dayComparison"]["new"]], ["今日新增"])
        self.assertEqual([item["title"] for item in enriched["dayComparison"]["continued"]], ["延续热点"])
        self.assertEqual([item["title"] for item in enriched["dayComparison"]["dropped"]], ["昨日热点"])


if __name__ == "__main__":
    unittest.main()
