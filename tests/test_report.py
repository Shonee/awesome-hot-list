import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.hotlist.report import (
    _extract_keywords,
    add_day_comparison,
    build_report,
    build_report_from_rows,
    load_rows,
)


class ReportBuilderTests(unittest.TestCase):
    def test_day_comparison_matches_rewrites_and_classifies_top_ten_movement(self):
        current = {
            "date": "2026-09-06",
            "metrics": {"slices": 1},
            "topTopics": [
                {"title": "今日新增热点", "url": "https://example.com/new", "hits": []},
                {"title": "西藏泥石流造成31人遇难 531人失联", "url": "https://example.com/rising", "hits": []},
                {"title": "位置保持不变", "url": "https://example.com/steady", "hits": []},
                {"title": "排名下降热点", "url": "https://example.com/falling", "hits": []},
            ],
        }
        previous = {
            "date": "2026-09-05",
            "metrics": {"slices": 1},
            "topTopics": [
                {"title": "排名下降热点", "url": "https://example.com/falling", "hits": []},
                {"title": "昨日掉榜热点", "url": "https://example.com/dropped", "hits": []},
                {"title": "位置保持不变", "url": "https://example.com/steady", "hits": []},
                {"title": "昨日占位热点", "url": "https://example.com/placeholder", "hits": []},
                {"title": "西藏泥石流31人遇难531人失联", "url": "https://example.com/rising-old", "hits": []},
            ],
        }

        add_day_comparison(current, previous)
        comparison = current["dayComparison"]

        self.assertEqual(
            comparison["counts"],
            {"new": 1, "continued": 3, "rising": 1, "falling": 1, "dropped": 2},
        )
        self.assertEqual(comparison["rising"][0]["title"], "西藏泥石流造成31人遇难 531人失联")
        self.assertEqual(comparison["rising"][0]["previousRank"], 5)
        self.assertEqual(comparison["rising"][0]["currentRank"], 2)
        self.assertEqual(comparison["rising"][0]["delta"], 3)
        self.assertEqual(comparison["falling"][0]["previousRank"], 1)
        self.assertEqual(comparison["falling"][0]["currentRank"], 4)
        self.assertEqual(comparison["falling"][0]["delta"], -3)

    def test_build_report_always_compares_with_the_previous_calendar_day(self):
        reports = {
            "2026-09-05": {
                "schemaVersion": 1,
                "date": "2026-09-05",
                "metrics": {"slices": 1},
                "topTopics": [{"title": "昨日热点", "url": "https://example.com/old", "hits": []}],
            },
            "2026-09-06": {
                "schemaVersion": 1,
                "date": "2026-09-06",
                "metrics": {"slices": 1},
                "topTopics": [{"title": "今日热点", "url": "https://example.com/new", "hits": []}],
            },
        }

        with (
            patch("src.hotlist.report.load_rows", side_effect=lambda date: {"date": date}),
            patch("src.hotlist.report.build_report_from_rows", side_effect=lambda date, _: reports[date]),
        ):
            report = build_report("2026-09-06")

        self.assertEqual(report["dayComparison"]["baselineDate"], "2026-09-05")
        self.assertEqual(report["dayComparison"]["counts"]["new"], 1)
        self.assertEqual(report["dayComparison"]["counts"]["dropped"], 1)

    def test_report_excludes_channels_marked_out_of_report(self):
        rows = {
            "weibo": [
                {"index": 1, "title": "公开热点", "url": "https://w.example/1"},
            ],
            "fuliba": [
                {"index": 1, "title": "隐藏内容", "url": "https://f.example/1"},
            ],
        }

        def definition(channel_id):
            return SimpleNamespace(
                channel_id=channel_id,
                name=channel_id,
                enabled_by_default=True,
                include_in_report=channel_id != "fuliba",
            )

        with (
            patch("src.hotlist.report.CHANNEL_ORDER", ("weibo", "fuliba")),
            patch("src.hotlist.report.get_channel", side_effect=definition),
            patch("src.hotlist.report.iter_channels", return_value=map(definition, ("weibo", "fuliba"))),
        ):
            report = build_report_from_rows("2026-09-04", rows)

        self.assertEqual(report["metrics"]["deduplicated"], 1)
        self.assertEqual(report["topTopics"][0]["title"], "公开热点")

    def test_load_rows_does_not_read_channels_excluded_from_reports(self):
        definitions = {
            "weibo": SimpleNamespace(include_in_report=True),
            "fuliba": SimpleNamespace(include_in_report=False),
        }

        with (
            patch("src.hotlist.report.CHANNEL_ORDER", ("weibo", "fuliba")),
            patch("src.hotlist.report.get_channel", side_effect=definitions.__getitem__),
            patch("src.hotlist.report.archive_path", side_effect=lambda channel_id, *_: f"{channel_id}.csv"),
            patch("src.hotlist.report.read_csv", return_value=[]) as read_rows,
        ):
            rows = load_rows("2026-09-04")

        self.assertEqual(rows, {"weibo": []})
        read_rows.assert_called_once_with("weibo.csv")

    def test_topic_ranking_uses_position_within_each_source_list(self):
        rows = {
            "weibo": [
                {
                    "index": rank,
                    "title": "长榜高百分位" if rank == 5 else "长榜占位",
                    "url": f"https://w.example/{rank}",
                    "datetime": "2026-09-04 12:00:00",
                }
                for rank in range(1, 101)
            ],
            "douyin": [
                {
                    "index": rank,
                    "title": "短榜绝对名次靠前" if rank == 2 else "短榜占位",
                    "url": f"https://d.example/{rank}",
                    "datetime": "2026-09-04 12:00:00",
                }
                for rank in range(1, 11)
            ],
        }

        report = build_report_from_rows("2026-09-04", rows)
        topic_titles = [item["title"] for item in report["topTopics"]]

        self.assertLess(topic_titles.index("长榜高百分位"), topic_titles.index("短榜绝对名次靠前"))

    def test_cross_channel_topic_outranks_repeated_single_channel_topic(self):
        rows = {
            "acfun": [
                {"index": 1, "title": "单渠道重复热点", "url": "https://a.example/1", "type": "日榜", "datetime": f"2026-09-04 {hour:02d}:00:00"}
                for hour in range(10)
            ],
            "weibo": [{"index": 8, "title": "跨渠道共同热点", "url": "https://w.example/1", "type": "热榜", "datetime": "2026-09-04 12:00:00"}],
            "toutiao": [{"index": 9, "title": "跨渠道共同热点", "url": "https://t.example/1", "type": "热榜", "datetime": "2026-09-04 12:00:00"}],
        }

        report = build_report_from_rows("2026-09-04", rows)

        self.assertEqual(report["topTopics"][0]["title"], "跨渠道共同热点")

    def test_report_deduplicates_titles_and_keeps_click_targets(self):
        rows = {
            "bilibili": [
                {"index": 5, "title": "共同热点", "url": "https://b.example/1", "type": "热榜", "datetime": "2026-09-04 09:00:00"},
                {"index": 2, "title": "共同热点", "url": "https://b.example/1", "type": "热榜", "datetime": "2026-09-04 12:00:00"},
            ],
            "douyin": [
                {"index": 3, "title": "共同热点", "url": "https://d.example/1", "type": "热搜", "datetime": "2026-09-04 12:00:00"},
                {"index": 1, "title": "独立热点", "url": "https://d.example/2", "type": "热搜", "datetime": "2026-09-04 12:00:00"},
            ],
        }

        report = build_report_from_rows("2026-09-04", rows)

        self.assertEqual(report["metrics"]["deduplicated"], 2)
        self.assertEqual(report["metrics"]["resonance"], 1)
        shared = next(item for item in report["topTopics"] if item["title"] == "共同热点")
        self.assertEqual(len(shared["hits"]), 2)
        self.assertEqual({hit["channelId"] for hit in shared["hits"]}, {"bilibili", "douyin"})

    def test_report_builds_curve_points_from_time_slices(self):
        rows = {
            "douyin": [
                {"index": 10, "title": "持续热点", "url": "https://example.com/1", "type": "热搜", "datetime": "2026-09-04 09:00:00"},
                {"index": 3, "title": "持续热点", "url": "https://example.com/1", "type": "热搜", "datetime": "2026-09-04 12:00:00"},
            ]
        }

        report = build_report_from_rows("2026-09-04", rows)

        curve = report["flow"]["rows"][0]
        self.assertEqual(report["flow"]["times"], ["09:00", "12:00"])
        self.assertEqual(curve["times"], ["09:00", "12:00"])
        self.assertEqual(curve["ranks"], [10, 3])
        self.assertEqual(curve["tone"], "up")

    def test_report_clusters_small_cross_channel_title_rewrites(self):
        rows = {
            "weibo": [{"index": 1, "title": "西藏泥石流31人遇难531人失联", "url": "https://w.example/1"}],
            "toutiao": [{"index": 2, "title": "西藏泥石流造成31人遇难 531人失联", "url": "https://t.example/1"}],
        }

        report = build_report_from_rows("2026-09-04", rows)

        self.assertEqual(report["metrics"]["deduplicated"], 1)
        self.assertEqual(report["metrics"]["resonance"], 1)

    def test_channel_timestamps_in_same_minute_share_one_curve_column(self):
        rows = {
            "weibo": [{"index": 1, "title": "甲热点事件标题", "url": "https://w.example/1", "datetime": "2026-09-04 09:00:01"}],
            "toutiao": [{"index": 2, "title": "乙热点事件标题", "url": "https://t.example/1", "datetime": "2026-09-04 09:00:58"}],
        }

        report = build_report_from_rows("2026-09-04", rows)

        self.assertEqual(report["flow"]["times"], ["09:00"])

    def test_unrelated_channel_sample_is_not_a_missing_rank(self):
        rows = {
            "weibo": [
                {"index": 1, "title": "微博热点事件", "url": "https://w.example/1", "datetime": "2026-09-04 09:00:00"},
            ],
            "toutiao": [
                {"index": 1, "title": "头条热点事件", "url": "https://t.example/1", "datetime": "2026-09-04 12:00:00"},
            ],
        }

        report = build_report_from_rows("2026-09-04", rows)
        weibo = next(row for row in report["flow"]["rows"] if row["topic"] == "微博热点事件")

        self.assertEqual(weibo["times"], ["09:00"])
        self.assertEqual(weibo["ranks"], [1])
        self.assertEqual(weibo["state"], "等待趋势")

    def test_single_observation_does_not_claim_a_trend(self):
        rows = {
            "weibo": [
                {
                    "index": 1,
                    "title": "单次采样热点",
                    "url": "https://w.example/1",
                    "datetime": "2026-09-04 09:00:01",
                }
            ]
        }

        report = build_report_from_rows("2026-09-04", rows)

        curve = report["flow"]["rows"][0]
        self.assertEqual(curve["state"], "等待趋势")
        self.assertEqual(curve["tone"], "pending")
        self.assertEqual(curve["tenure"], "1 个切片")
        self.assertEqual(report["signals"], [])

    def test_report_marks_missing_later_slice_as_dropped(self):
        rows = {
            "weibo": [
                {"index": 2, "title": "稍后掉榜的热点", "url": "https://w.example/1", "type": "热榜", "datetime": "2026-09-04 09:00:00"},
                {"index": 1, "title": "替代热点事件", "url": "https://w.example/2", "type": "热榜", "datetime": "2026-09-04 12:00:00"},
            ]
        }

        report = build_report_from_rows("2026-09-04", rows)
        curve = next(row for row in report["flow"]["rows"] if row["topic"] == "稍后掉榜的热点")

        self.assertEqual(curve["times"], ["09:00", "12:00"])
        self.assertEqual(curve["ranks"], [2, None])
        self.assertEqual(curve["tone"], "dropped")

    def test_report_marks_missing_earlier_slice_as_new(self):
        rows = {
            "weibo": [
                {"index": 1, "title": "原有热点事件", "url": "https://w.example/1", "type": "热榜", "datetime": "2026-09-04 09:00:00"},
                {"index": 2, "title": "后来新进热点", "url": "https://w.example/2", "type": "热榜", "datetime": "2026-09-04 12:00:00"},
            ]
        }

        report = build_report_from_rows("2026-09-04", rows)
        curve = next(row for row in report["flow"]["rows"] if row["topic"] == "后来新进热点")

        self.assertEqual(curve["ranks"], [None, 2])
        self.assertEqual(curve["tone"], "new")

    def test_report_marks_topic_returning_after_gap_as_reentered(self):
        rows = {
            "weibo": [
                {"index": 2, "title": "重新进入榜单热点", "url": "https://w.example/1", "type": "热榜", "datetime": "2026-09-04 09:00:00"},
                {"index": 1, "title": "中间替代热点", "url": "https://w.example/2", "type": "热榜", "datetime": "2026-09-04 10:00:00"},
                {"index": 3, "title": "重新进入榜单热点", "url": "https://w.example/1", "type": "热榜", "datetime": "2026-09-04 11:00:00"},
            ]
        }

        report = build_report_from_rows("2026-09-04", rows)
        curve = next(row for row in report["flow"]["rows"] if row["topic"] == "重新进入榜单热点")

        self.assertEqual(curve["ranks"], [2, None, 3])
        self.assertEqual(curve["tone"], "reentered")

    def test_keyword_extraction_filters_stop_word_fragments(self):
        records = [
            ("weibo", {"title": "为什么新品发布了一天就更新"}),
            ("toutiao", {"title": "为什么新品发布了一天就更新"}),
            ("github", {"title": "..."}),
        ]

        words = {word for word, _ in _extract_keywords(records)}

        self.assertNotIn("为什", words)
        self.assertNotIn("了一", words)
        self.assertNotIn("...", words)

    def test_coverage_never_exceeds_one_hundred_percent(self):
        rows = {
            channel_id: [{"index": 1, "title": f"{channel_id} 热点内容", "url": f"https://example.com/{channel_id}"}]
            for channel_id in ("bilibili", "zhihu", "maimai", "xueqiu", "linuxdo")
        }

        report = build_report_from_rows("2026-09-04", rows)

        self.assertLessEqual(report["metrics"]["coverage"], 100)

    def test_sampling_coverage_uses_channel_frequency_and_unique_collection_times(self):
        rows = {
            "hourly": [
                {"index": 1, "title": "早间热点", "url": "https://example.com/1", "datetime": "2026-09-04 08:00:00"},
                {"index": 1, "title": "午间热点", "url": "https://example.com/2", "datetime": "2026-09-04 12:00:00"},
            ],
            "special": [
                {"index": 1, "title": "低频热点", "url": "https://example.com/3", "datetime": "2026-09-04 12:00:00"},
            ],
        }

        def definition(channel_id):
            return SimpleNamespace(
                channel_id=channel_id,
                name=channel_id,
                enabled_by_default=True,
                include_in_report=True,
                frequency_minutes=60 if channel_id == "hourly" else 360,
            )

        with (
            patch("src.hotlist.report.CHANNEL_ORDER", ("hourly", "special")),
            patch("src.hotlist.report.get_channel", side_effect=definition),
            patch("src.hotlist.report.iter_channels", return_value=map(definition, ("hourly", "special"))),
            patch(
                "src.hotlist.report.project_now",
                return_value=datetime(2026, 9, 4, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            ),
        ):
            report = build_report_from_rows("2026-09-04", rows)

        self.assertEqual(report["metrics"]["coverage"], 100)
        self.assertEqual(report["metrics"]["samplingCoverage"], 19)

    def test_topic_score_prefers_a_topic_present_in_the_latest_slice(self):
        rows = {
            "weibo": [
                {"index": 1, "title": "AAA早已掉榜热点", "url": "https://example.com/old", "datetime": "2026-09-04 09:00:00"},
                {"index": 1, "title": "中间占位热点", "url": "https://example.com/mid", "datetime": "2026-09-04 10:00:00"},
                {"index": 1, "title": "ZZZ仍在榜热点", "url": "https://example.com/current", "datetime": "2026-09-04 11:00:00"},
            ]
        }

        report = build_report_from_rows("2026-09-04", rows)

        titles = [topic["title"] for topic in report["topTopics"]]
        self.assertLess(titles.index("ZZZ仍在榜热点"), titles.index("AAA早已掉榜热点"))


if __name__ == "__main__":
    unittest.main()
