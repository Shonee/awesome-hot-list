import json
import tempfile
import unittest
import warnings
from datetime import datetime
from unittest.mock import patch
from pathlib import Path
from zoneinfo import ZoneInfo

from src.hotlist.channels import bing, cls, readhub, sina, wallstreetcn
from src.hotlist.channels.common import clean_html, select_live_items
from src.hotlist.models import ChannelSnapshot, HotItem, Ranking
from src.hotlist.report import build_report_from_rows
from src.hotlist.runner import collect_channels, merge_latest_snapshot


SHANGHAI = ZoneInfo("Asia/Shanghai")


class RankingSurfaceTests(unittest.TestCase):
    def test_surface_is_serialized_and_archived(self):
        ranking = Ranking("live", "7x24", [HotItem(1, "快讯", "https://example.com/1")], surface="live")

        self.assertEqual(ranking.to_dict()["surface"], "live")

    def test_report_ignores_non_hotlist_rows(self):
        rows = {
            "sina": [
                {"index": 1, "title": "热榜内容", "url": "https://example.com/hot", "surface": "hotlist"},
                {"index": 1, "title": "滚动快讯", "url": "https://example.com/live", "surface": "live"},
            ]
        }

        report = build_report_from_rows("2026-09-17", rows)

        self.assertEqual(report["metrics"]["deduplicated"], 1)
        self.assertEqual(report["topTopics"][0]["title"], "热榜内容")

    def test_partial_live_merge_preserves_existing_hot_rankings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(json.dumps({"channels": [{
                "channelId": "sina",
                "rankings": [{"id": "news", "name": "新闻热榜", "surface": "hotlist", "items": [{"title": "热点"}]}],
                "status": "ok",
            }]}), encoding="utf-8")
            snapshot = ChannelSnapshot(
                "sina",
                "新浪",
                "https://news.sina.com.cn/",
                "2026-09-17 13:00:00",
                [Ranking("live", "7x24", [HotItem(1, "快讯", "https://example.com/live")], surface="live")],
            )

            payload = merge_latest_snapshot([snapshot], str(path), preserve_existing_rankings=True)

        self.assertEqual([item["id"] for item in payload["channels"][0]["rankings"]], ["news", "live"])

    def test_live_collection_uses_surface_specific_collector(self):
        snapshot = ChannelSnapshot(
            "sina",
            "新浪",
            "https://news.sina.com.cn/",
            "2026-09-17 13:00:00",
            [Ranking("live", "7x24", [HotItem(1, "快讯", "https://example.com/live")], surface="live")],
        )
        with patch("src.hotlist.channels.collect_channel", return_value=snapshot) as collect:
            result = collect_channels(["sina"], surface="live")

        collect.assert_called_once_with("sina", surface="live")
        self.assertIs(result[0], snapshot)


class LiveWindowTests(unittest.TestCase):
    def _item(self, minute):
        return HotItem(
            minute + 1,
            f"快讯 {minute}",
            f"https://example.com/{minute}",
            published_at=f"2026-09-17 12:{minute:02d}:00",
        )

    def test_uses_three_hours_when_at_most_one_hundred_items(self):
        now = datetime(2026, 9, 17, 13, 0, tzinfo=SHANGHAI)
        rows = [self._item(minute) for minute in range(60)]

        selected = select_live_items(rows, now=now)

        self.assertEqual(len(selected), 60)
        self.assertEqual(selected[0].published_at, "2026-09-17 12:59:00")

    def test_switches_to_one_hour_and_caps_at_one_hundred(self):
        now = datetime(2026, 9, 17, 13, 0, tzinfo=SHANGHAI)
        rows = [
            HotItem(index + 1, f"快讯 {index}", f"https://example.com/{index}", published_at=f"2026-09-17 12:{index // 3:02d}:{(index % 3) * 20:02d}")
            for index in range(150)
            if index // 3 < 60
        ]

        selected = select_live_items(rows, now=now)

        self.assertEqual(len(selected), 100)
        self.assertGreaterEqual(selected[-1].published_at, "2026-09-17 12:00:00")


class LiveParserTests(unittest.TestCase):
    def test_clean_html_does_not_emit_filename_warnings_for_plain_news_text(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = clean_html("updates/market-report.html")

        self.assertEqual(result, "updates/market-report.html")
        self.assertEqual(caught, [])

    def test_sina_live_collection_does_not_request_hot_rankings(self):
        payload = {"result": {"data": {"feed": {"list": [{
            "id": 42,
            "rich_text": "新浪快讯",
            "create_time": "2026-09-17 12:30:00",
            "docurl": "https://finance.sina.cn/7x24/example.d.html",
        }]}}}}
        with (
            patch.object(sina, "get", return_value=payload) as request,
            patch.object(sina, "select_live_items", side_effect=lambda items: items),
        ):
            result = sina.collect_live()

        request.assert_called_once_with(sina.LIVE_API_URL, res_type="json", timeout=20, retries=1)
        self.assertEqual([ranking.surface for ranking in result.rankings], ["live"])

    def test_cls_live_collection_does_not_request_homepage(self):
        payload = {"errno": 0, "data": {"roll_data": [{
            "id": 7,
            "content": "财联社快讯",
            "ctime": 1789619400,
        }]}}
        with (
            patch.object(cls, "get", return_value=payload) as request,
            patch.object(cls, "select_live_items", side_effect=lambda items: items),
        ):
            result = cls.collect_live()

        self.assertIn("name=telegraph", request.call_args.args[0])
        self.assertEqual([ranking.surface for ranking in result.rankings], ["live"])

    def test_sina_live_parser_reads_official_payload(self):
        payload = {"result": {"data": {"feed": {"list": [{
            "id": 42,
            "rich_text": "【市场快讯】测试内容",
            "create_time": "2026-09-17 12:30:00",
            "docurl": "https://finance.sina.cn/7x24/example.d.html",
        }]}}}}

        items = sina.parse_live_payload(payload)

        self.assertEqual(items[0].title, "【市场快讯】测试内容")
        self.assertEqual(items[0].published_at, "2026-09-17 12:30:00")

    def test_cls_live_parser_uses_content_when_title_is_empty(self):
        payload = {"errno": 0, "data": {"roll_data": [{
            "id": 7,
            "title": "",
            "content": "财联社测试快讯",
            "ctime": 1789619400,
        }]}}

        items = cls.parse_live_payload(payload)

        self.assertEqual(items[0].title, "财联社测试快讯")
        self.assertEqual(items[0].url, "https://www.cls.cn/detail/7")

    def test_wallstreetcn_parser_normalizes_live_items(self):
        payload = {"data": {"items": [{
            "id": 9,
            "title": "",
            "content_text": "见闻测试快讯",
            "display_time": 1789619400,
            "uri": "https://wallstreetcn.com/livenews/9",
        }]}}

        items = wallstreetcn.parse_live_payload(payload)

        self.assertEqual(items[0].title, "见闻测试快讯")
        self.assertEqual(items[0].url, "https://wallstreetcn.com/livenews/9")


class NewSourceParserTests(unittest.TestCase):
    def test_bing_reads_domestic_homepage_topics(self):
        html = '<div id="tobPrompt"><a href="/search?q=%E5%9B%BD%E5%86%85"><span class="tob_title">国内热点新闻</span></a></div>'

        items = bing.parse_domestic_trending(html)

        self.assertEqual(items[0].title, "国内热点新闻")
        self.assertIn("bing.com/search", items[0].url)

    def test_bing_rejects_non_chinese_topic_sets(self):
        html = '<div id="tobPrompt"><a href="/search?q=test"><span class="tob_title">Tokyo News</span></a></div>'

        self.assertEqual(bing.parse_domestic_trending(html), [])

    def test_readhub_parses_daily_hot_and_ai_lists(self):
        daily = '<a href="/daily/2026-09-16">09.16 每日早报标题 12 条</a>'
        hot = '<div><a href="/topic/def?tab=daily">热点排行榜标题</a></div>'
        ai = '<article><a target="_blank" href="https://news.example/a">AI 资讯标题</a><span>摘要</span></article>'

        self.assertEqual(readhub.parse_daily_links(daily)[0].title, "09.16 每日早报标题 12 条")
        self.assertEqual(readhub.parse_daily_links(daily)[0].published_at, "2026-09-16")
        self.assertEqual(readhub.parse_topic_links(hot)[0].title, "热点排行榜标题")
        self.assertEqual(readhub.parse_ai_news(ai)[0].description, "摘要")

    def test_readhub_ai_parser_ignores_footer_links(self):
        html = '<footer><a target="_blank" href="https://example.com/legal">很长的备案说明文字</a></footer>'

        self.assertEqual(readhub.parse_ai_news(html), [])


if __name__ == "__main__":
    unittest.main()
