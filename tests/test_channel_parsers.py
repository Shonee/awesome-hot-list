import unittest

from src.hotlist.channels import (
    parse_36kr,
    parse_acfun,
    parse_bilibili_hot_search,
    parse_bilibili_videos,
    parse_cls_hot_articles,
    parse_douban,
    parse_hupu,
    parse_juejin,
    parse_rss,
    parse_questions,
    parse_toutiao,
    parse_weibo,
    parse_xueqiu,
    parse_v2ex,
)


class JsonChannelParserTests(unittest.TestCase):
    def test_bilibili_hot_search_parser_normalizes_items(self):
        items = parse_bilibili_hot_search(
            {"data": {"list": [{"keyword": "B站热点", "show_name": "B站热点说明"}]}}
        )
        self.assertEqual(items[0].title, "B站热点")
        self.assertEqual(items[0].url, "https://search.bilibili.com/all?keyword=B%E7%AB%99%E7%83%AD%E7%82%B9")
        self.assertEqual(items[0].description, "B站热点说明")

    def test_bilibili_video_parser_supports_short_link_and_fallback(self):
        items = parse_bilibili_videos(
            {
                "data": {
                    "list": [
                        {"title": "热门视频", "short_link_v2": "https://b23.tv/demo", "stat": {"view": 99}},
                        {"title": "无短链视频", "bvid": "BVdemo", "stat": {}, "pic": "cover"},
                    ]
                }
            }
        )
        self.assertEqual(items[0].url, "https://b23.tv/demo")
        self.assertEqual(items[0].hot, 99)
        self.assertEqual(items[1].url, "https://www.bilibili.com/video/BVdemo")
        self.assertEqual(items[1].image_url, "cover")

    def test_toutiao_parser_uses_public_board_fields(self):
        items = parse_toutiao(
            {"data": [{"Title": "头条热点", "Url": "https://example.com/t", "HotValue": 900}]}
        )
        self.assertEqual(items[0].title, "头条热点")
        self.assertEqual(items[0].hot, 900)

    def test_weibo_parser_reads_realtime_endpoint(self):
        items = parse_weibo({"data": {"realtime": [{"word": "微博热点", "num": 123}]}})
        self.assertEqual(items[0].title, "微博热点")
        self.assertEqual(items[0].hot, 123)

    def test_acfun_parser_accepts_rank_list(self):
        payload = {
            "rankList": [
                {"contentTitle": "A站视频", "contentId": 123, "viewCount": 88, "coverUrl": "cover"}
            ]
        }
        items = parse_acfun(payload)
        self.assertEqual(items[0].url, "https://www.acfun.cn/v/ac123")
        self.assertEqual(items[0].image_url, "cover")

    def test_36kr_parser_reads_nested_material(self):
        payload = {
            "data": {
                "hotRankList": [
                    {"itemId": "42", "templateMaterial": {"widgetTitle": "创业新闻", "statRead": 12}}
                ]
            }
        }
        items = parse_36kr(payload)
        self.assertEqual(items[0].title, "创业新闻")
        self.assertEqual(items[0].url, "https://www.36kr.com/p/42")

    def test_xueqiu_parser_removes_topic_markers(self):
        items = parse_xueqiu({"list": [{"id": 7, "tag": "#市场热点#", "status_count": 66}]})
        self.assertEqual(items[0].title, "市场热点")
        self.assertEqual(items[0].hot, 66)

    def test_stackoverflow_parser_normalizes_question_metrics(self):
        items = parse_questions(
            {
                "items": [
                    {
                        "title": "How do I use &amp; in Python?",
                        "link": "https://stackoverflow.com/questions/42/demo",
                        "score": 12,
                        "answer_count": 3,
                        "view_count": 456,
                        "creation_date": 1788523206,
                    }
                ]
            }
        )
        self.assertEqual(items[0].title, "How do I use & in Python?")
        self.assertEqual(items[0].hot, 12)
        self.assertEqual(items[0].description, "3 个回答 · 456 次浏览")
        self.assertEqual(items[0].url, "https://stackoverflow.com/questions/42/demo")

    def test_v2ex_parser_builds_topic_url_and_uses_replies(self):
        items = parse_v2ex(
            [{
                "id": 99,
                "title": "V2EX 热门主题",
                "replies": 21,
                "last_modified": 1788523206,
                "node": {"title": "分享创造"},
            }]
        )
        self.assertEqual(items[0].url, "https://www.v2ex.com/t/99")
        self.assertEqual(items[0].hot, 21)
        self.assertEqual(items[0].description, "分享创造")

    def test_cls_parser_reads_next_data_hot_articles(self):
        html = '''<script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"hotArticleData":[{"id":7,"title":"财经快讯","brief":"摘要","ctime":1788523206,"readNum":88,"img":"cover"}]}}}
        </script>'''
        items = parse_cls_hot_articles(html)
        self.assertEqual(items[0].title, "财经快讯")
        self.assertEqual(items[0].url, "https://www.cls.cn/detail/7")
        self.assertEqual(items[0].hot, 88)
        self.assertEqual(items[0].description, "摘要")


class MarkupParserTests(unittest.TestCase):
    def test_rss_parser_supports_rss_and_atom_links(self):
        rss = """<?xml version="1.0"?><rss><channel><title>测试源</title><item>
        <title>RSS 新闻</title><link>https://example.com/rss</link><description>摘要</description>
        </item></channel></rss>"""
        name, items = parse_rss(rss, "https://example.com/feed")
        self.assertEqual(name, "测试源")
        self.assertEqual(items[0].description, "摘要")

    def test_rss_parser_sorts_by_time_and_limits_items(self):
        rss = """<?xml version="1.0"?><rss><channel><title>测试源</title>
        <item><title>旧</title><link>https://example.com/old</link><pubDate>Mon, 01 Sep 2026 10:00:00 GMT</pubDate></item>
        <item><title>新</title><link>https://example.com/new</link><pubDate>Wed, 03 Sep 2026 10:00:00 GMT</pubDate></item>
        </channel></rss>"""
        name, items = parse_rss(rss, "https://example.com/feed", limit=1)
        self.assertEqual(name, "测试源")
        self.assertEqual([item.title for item in items], ["新"])

    def test_douban_parser_extracts_group_topics(self):
        html = """<div class="channel-item"><h3><a href="https://douban.com/1">豆瓣话题</a></h3>
        <div class="content">话题摘要</div></div>"""
        items = parse_douban(html)
        self.assertEqual(items[0].title, "豆瓣话题")
        self.assertEqual(items[0].description, "话题摘要")

    def test_hupu_parser_handles_relative_links(self):
        html = """<div class="t-info"><a href="/123.html"><span class="t-title">虎扑帖子</span></a>
        <span class="t-replies">100回复</span></div>"""
        items = parse_hupu(html)
        self.assertEqual(items[0].url, "https://bbs.hupu.com/123.html")
        self.assertEqual(items[0].hot, "100回复")

    def test_hupu_parser_reads_mobile_ssr_payload(self):
        html = '''<script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"res":[{"tagId":7,"tagName":"热门赛事","heat":1234,"rank":1,"tagUpdateDesc":"每10分钟更新一次"}]}}}
        </script>'''
        items = parse_hupu(html)
        self.assertEqual(items[0].title, "热门赛事")
        self.assertEqual(items[0].hot, 1234)
        self.assertIn("tagId=7", items[0].url)

    def test_juejin_parser_reads_rank_response(self):
        payload = {
            "data": [
                {
                    "content": {"content_id": "123", "title": "掘金热门文章"},
                    "content_counter": {"hot_rank": 88},
                }
            ]
        }
        items = parse_juejin(payload)
        self.assertEqual(items[0].title, "掘金热门文章")
        self.assertEqual(items[0].url, "https://juejin.cn/post/123")
        self.assertEqual(items[0].hot, 88)


if __name__ == "__main__":
    unittest.main()
