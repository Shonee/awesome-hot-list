import json
import unittest
from unittest.mock import call, patch

from src.hotlist.channels import baidu, eastmoney, googletrends, hackernews
from src.hotlist.channels import huggingface, kuaishou, lobsters, netease, sina, thepaper
from src.hotlist.registry import SPECIAL_CHANNELS, get_channel


class FirstBatchParserTests(unittest.TestCase):
    def test_baidu_reads_structured_hot_list_payload(self):
        payload = {
            "data": {"cards": [{"component": "hotList", "content": [
                {"index": 0, "word": "百度热点", "url": "https://www.baidu.com/s?wd=hot", "hotScore": "9988", "desc": "摘要", "img": "cover"}
            ]}]}
        }
        items = baidu.parse_hot_list(f"<html><!--s-data:{json.dumps(payload, ensure_ascii=False)}--></html>")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].rank, 1)
        self.assertEqual(items[0].title, "百度热点")
        self.assertEqual(items[0].hot, 9988)
        self.assertEqual(items[0].description, "摘要")

    def test_netease_reads_official_flow(self):
        items = netease.parse_news_flow({"code": 200, "data": {"list": [{
            "title": "网易新闻", "url": "https://m.163.com/news/article/1.html",
            "source": "网易号", "publishTime": "2026-09-14 10:00:00", "imgsrc": "cover",
        }]}})

        self.assertEqual(items[0].title, "网易新闻")
        self.assertEqual(items[0].description, "网易号")
        self.assertEqual(items[0].published_at, "2026-09-14 10:00:00")

    def test_sina_reads_javascript_wrapped_rankings(self):
        body = 'var data = {"data":[{"title":"新浪热点","url":"https://news.sina.com.cn/a","top_num":"12,345","time":"Sun, 13 Sep 2026 23:20:24 +0800","media":"新浪"}]};'
        items = sina.parse_top_data(body)

        self.assertEqual(items[0].title, "新浪热点")
        self.assertEqual(items[0].hot, 12345)
        self.assertEqual(items[0].description, "新浪")

    @patch("src.hotlist.channels.sina.get")
    def test_sina_collects_news_and_finance_in_one_card(self, request):
        request.side_effect = [
            'var data = {"data":[{"title":"新闻","url":"https://news.sina.com.cn/1"}]};',
            'var data = {"data":[{"title":"财经","url":"https://finance.sina.com.cn/1"}]};',
            {"result": {"data": {"feed": {"list": []}}}},
        ]

        result = sina.collect()

        self.assertEqual([ranking.ranking_id for ranking in result.rankings], ["news", "finance", "live"])
        self.assertEqual([ranking.name for ranking in result.rankings], ["新闻热榜", "财经热榜", "7x24"])
        self.assertEqual(result.rankings[-1].surface, "live")
        self.assertTrue(all(ranking.provider_name == "新浪官方" for ranking in result.rankings))
        self.assertIn("top.news.sina.com.cn", request.call_args_list[0].args[0])
        self.assertIn("top.finance.sina.com.cn", request.call_args_list[1].args[0])
        self.assertIn("app.cj.sina.com.cn", request.call_args_list[2].args[0])

    @patch("src.hotlist.channels.eastmoney.get")
    @patch("src.hotlist.channels.eastmoney.post")
    def test_eastmoney_uses_one_batch_quote_request(self, request_rank, request_quotes):
        request_rank.return_value = {"data": [
            {"sc": "SZ000823", "rk": 1, "rc": 1},
            {"sc": "SH600519", "rk": 2, "rc": -1},
        ]}
        request_quotes.return_value = {"data": {"diff": [
            {"f12": "000823", "f14": "超声电子", "f2": 2263, "f3": 1001},
            {"f12": "600519", "f14": "贵州茅台", "f2": 160000, "f3": -120},
        ]}}

        result = eastmoney.collect()

        self.assertEqual([item.title for item in result.rankings[0].items], ["超声电子 (000823)", "贵州茅台 (600519)"])
        self.assertEqual(request_rank.call_count, 1)
        self.assertEqual(request_quotes.call_count, 1)
        self.assertIn("secids=0.000823%2C1.600519", request_quotes.call_args.args[0])

    @patch("src.hotlist.channels.eastmoney.get", side_effect=RuntimeError("quote unavailable"))
    @patch("src.hotlist.channels.eastmoney.post")
    def test_eastmoney_keeps_rank_when_quote_enrichment_fails(self, request_rank, _request_quotes):
        request_rank.return_value = {"data": [{"sc": "SZ000823", "rk": 1, "rc": 1}]}

        result = eastmoney.collect()

        self.assertEqual(result.rankings[0].items[0].title, "000823 (000823)")
        self.assertIn("行情增强失败", result.warnings[0])

    @patch("src.hotlist.channels.hackernews.get")
    def test_hackernews_limits_detail_requests(self, request):
        def response(url, **_kwargs):
            if url == hackernews.TOP_STORIES_URL:
                return list(range(100, 200))
            story_id = int(url.rsplit("/", 1)[-1].split(".", 1)[0])
            return {"id": story_id, "type": "story", "title": f"Story {story_id}", "score": story_id, "url": f"https://example.com/{story_id}"}

        request.side_effect = response
        result = hackernews.collect()

        self.assertEqual(len(result.rankings[0].items), hackernews.OUTPUT_LIMIT)
        self.assertLessEqual(request.call_count, hackernews.DETAIL_LIMIT + 1)

    @patch("src.hotlist.channels.hackernews.get")
    def test_hackernews_skips_one_failed_story_request(self, request):
        request.side_effect = [
            [100, 101],
            RuntimeError("one story failed"),
            {"id": 101, "type": "story", "title": "Still works", "score": 1},
        ]

        result = hackernews.collect()

        self.assertEqual([item.title for item in result.rankings[0].items], ["Still works"])


class SecondBatchParserTests(unittest.TestCase):
    def test_thepaper_only_reads_article_nodes(self):
        payload = {"data": {"hotNews": [
            {"name": "栏目节点"},
            {"contId": "123", "name": "澎湃热点", "praiseTimes": "88", "interactionNum": "12", "pubTime": "2小时前", "pic": "cover"},
        ]}}
        items = thepaper.parse_hot_news(payload)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://www.thepaper.cn/newsDetail_forward_123")
        self.assertEqual(items[0].hot, 100)

    def test_lobsters_reads_hottest_json(self):
        items = lobsters.parse_hottest([{
            "short_id": "abc", "title": "Lobsters story", "url": "https://example.com/story",
            "score": 42, "comment_count": 7, "created_at": "2026-09-14T01:00:00Z", "tags": ["python", "web"],
        }])

        self.assertEqual(items[0].hot, 42)
        self.assertIn("7 comments", items[0].description)

    def test_huggingface_reads_trending_models(self):
        items = huggingface.parse_models([{
            "id": "openai/demo", "trendingScore": 321, "downloads": 999,
            "likes": 12, "pipeline_tag": "text-generation", "lastModified": "2026-09-14T00:00:00Z",
        }])

        self.assertEqual(items[0].title, "openai/demo")
        self.assertEqual(items[0].hot, 321)
        self.assertIn("999 downloads", items[0].description)


class CandidateSourceTests(unittest.TestCase):
    def test_actions_verified_candidates_are_enabled_and_reported(self):
        for channel_id in ("kuaishou", "huggingface"):
            definition = get_channel(channel_id)
            with self.subTest(channel=channel_id):
                self.assertTrue(definition.enabled_by_default)
                self.assertTrue(definition.visible_by_default)
                self.assertTrue(definition.include_in_report)
                self.assertIn(channel_id, SPECIAL_CHANNELS)

    def test_google_trends_reads_official_embedded_data(self):
        data = [None, [["任正非", None, "HK", [1789302600], None, None, 5000, None, 1000, ["任正非 最新消息"]]]]
        html = "<script>AF_initDataCallback({key: 'ds:0', hash: '2', data:" + json.dumps(data, ensure_ascii=False) + ", sideChannel: {}});</script>"

        items = googletrends.parse_trending_page(html)

        self.assertEqual(items[0].title, "任正非")
        self.assertEqual(items[0].hot, 5000)
        self.assertIn("geo=HK", items[0].url)
        self.assertEqual(items[0].published_at, "2026-09-13 12:30:00")

    def test_kuaishou_reads_official_apollo_state(self):
        state = {"defaultClient": {
            "ROOT_QUERY": {"visionHotRank({\"page\":\"home\"})": {"id": "$hot"}},
            "$hot": {"result": 1, "items": [{"id": "VisionHotRankItem:热点"}]},
            "VisionHotRankItem:热点": {"rank": 1, "name": "快手热点", "hotValue": "999万", "poster": "cover", "photoIds": {"json": ["photo1"]}},
        }}
        html = "<script>window.__APOLLO_STATE__=" + json.dumps(state, ensure_ascii=False) + ";</script>"
        items = kuaishou.parse_official_page(html)

        self.assertEqual(items[0].rank, 1)
        self.assertEqual(items[0].title, "快手热点")
        self.assertEqual(items[0].hot, "999万")
        self.assertIn("photo1", items[0].url)

    def test_kuaishou_reads_dailyhot_fallback(self):
        items = kuaishou.parse_dailyhot({"code": 200, "data": [{
            "title": "第三方快手热点", "url": "https://www.kuaishou.com/short-video/1", "hot": "100万",
        }]})

        self.assertEqual(items[0].title, "第三方快手热点")
        self.assertEqual(items[0].hot, "100万")

    @patch("src.hotlist.channels.kuaishou.fetch_dailyhot")
    @patch("src.hotlist.channels.kuaishou.get")
    def test_kuaishou_prefers_official_page(self, request, fallback):
        state = {"defaultClient": {
            "ROOT_QUERY": {"visionHotRank({\"page\":\"home\"})": {"id": "$hot"}},
            "$hot": {"result": 1, "items": [{"id": "VisionHotRankItem:热点"}]},
            "VisionHotRankItem:热点": {"rank": 1, "name": "官方热点", "hotValue": "1万"},
        }}
        request.return_value = "window.__APOLLO_STATE__=" + json.dumps(state, ensure_ascii=False) + ";"

        result = kuaishou.collect()

        self.assertEqual(result.rankings[0].provider_name, "快手官方")
        fallback.assert_not_called()

    @patch("src.hotlist.channels.kuaishou.fetch_dailyhot")
    @patch("src.hotlist.channels.kuaishou.fetch_tophub_ranking")
    @patch("src.hotlist.channels.kuaishou.get", return_value="no state")
    def test_kuaishou_falls_back_to_tophub(self, _request, tophub_fallback, dailyhot_fallback):
        from src.hotlist.models import HotItem

        tophub_fallback.return_value = [HotItem(1, "今日热榜快手", "https://index.e.kuaishou.com/1")]

        result = kuaishou.collect()

        self.assertEqual(result.rankings[0].provider_name, "今日热榜")
        dailyhot_fallback.assert_not_called()

    @patch("src.hotlist.channels.kuaishou.fetch_dailyhot")
    @patch("src.hotlist.channels.kuaishou.fetch_tophub_ranking", side_effect=RuntimeError("tophub down"))
    @patch("src.hotlist.channels.kuaishou.get", return_value="no state")
    def test_kuaishou_uses_dailyhot_as_last_fallback(self, _request, _tophub_fallback, dailyhot_fallback):
        dailyhot_fallback.return_value = [{"title": "DailyHot 快手", "url": "https://www.kuaishou.com/1"}]

        result = kuaishou.collect()

        self.assertEqual(result.rankings[0].provider_name, "DailyHot API")


if __name__ == "__main__":
    unittest.main()
