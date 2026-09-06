import unittest

from src.hotlist.report import _extract_keywords, build_report_from_rows


class ReportBuilderTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
