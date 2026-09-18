import unittest
from unittest.mock import patch

from src.hotlist.channels import autohome, gamersky, ithome, yicai


class OfficialSourceParserTests(unittest.TestCase):
    def test_autohome_uses_daily_hot_rank_and_source_links(self):
        payload = {"result": {"rankList": [
            {"rank": 2, "title": "汽车热点", "url": "http://www.autohome.com.cn/news/202609/1.html", "hotScore": 123},
            {"rank": 3, "title": "异站广告", "url": "https://example.com/ad", "hotScore": 999},
            {"rank": 4, "title": "车家号热点", "url": "https://mf.autohome.com.cn/v3/2"},
        ]}}
        items = autohome.parse_hot_rank(payload)
        self.assertEqual([item.title for item in items], ["汽车热点", "车家号热点"])
        self.assertEqual(items[0].rank, 2)
        self.assertEqual(items[0].hot, 123)

    def test_gamersky_only_reads_ranked_news_sidebar(self):
        html = '''<a href="/news/202609/1.shtml">普通新闻</a>
        <div class="Mid2_R"><div class="tit">热点资讯排行</div>
        <ul class="Mid2Rtxt"><li><div class="num">1</div>
        <a href="https://www.gamersky.com/news/202609/2.shtml">热门新闻</a></li>
        <li><div class="num">2</div><a href="https://example.com/ad">广告</a></li></ul></div>'''
        items = gamersky.parse_hot_news(html)
        self.assertEqual([(item.rank, item.title) for item in items], [(1, "热门新闻")])

    def test_ithome_reads_daily_ranking_only(self):
        html = '''<a href="https://www.ithome.com/1/111/111.htm">首页推荐</a>
        <div id="rank"><ul id="d-1"><li><a href="https://www.ithome.com/1/222/222.htm" title="日榜新闻">日榜新闻</a></li></ul>
        <ul id="d-2"><li><a href="https://www.ithome.com/1/333/333.htm">周榜新闻</a></li></ul></div>'''
        self.assertEqual([item.title for item in ithome.parse_daily_rank(html)], ["日榜新闻"])

    def test_yicai_separates_homepage_headlines_and_live_briefs(self):
        html = '''<div class="swiper-wrapper"><div class="swiper-slide item">
        <a href="/news/123.html"><h2 class="m-tips1">首页头条</h2></a></div></div>
        <div id="scrollFontDiv"><a href="/brief/456.html">滚动快讯</a></div>'''
        self.assertEqual([item.title for item in yicai.parse_headlines(html)], ["首页头条"])
        rows = [
            {"LiveTitle": "较旧快讯", "LiveID": 2, "CreateDate": "2026-09-17T10:00:00", "ShareUrl": "https://m.yicai.com/brief/2.html"},
            {"LiveTitle": "最新快讯", "LiveID": 3, "CreateDate": "2026-09-17T10:02:00", "ShareUrl": "https://m.yicai.com/brief/3.html"},
            {"LiveTitle": "广告", "LiveID": 4, "ShareUrl": "https://example.com/ad"},
        ]
        items = yicai.parse_live_payload(rows)
        self.assertEqual([item.title for item in items], ["最新快讯", "较旧快讯"])
        self.assertEqual(items[0].published_at, "2026-09-17T10:02:00")

    def test_yicai_homepage_survives_live_failure(self):
        html = '<div class="swiper-wrapper"><div class="swiper-slide item"><a href="/news/123.html"><h2 class="m-tips1">首页头条</h2></a></div></div>'
        with patch.object(yicai, "get", return_value=html), patch.object(yicai, "collect_live", side_effect=RuntimeError("live down")):
            result = yicai.collect()
        self.assertEqual(result.rankings[0].items[0].title, "首页头条")
        self.assertEqual(result.rankings[1].surface, "live")
        self.assertEqual(result.warnings, ["7x24"])


if __name__ == "__main__":
    unittest.main()
