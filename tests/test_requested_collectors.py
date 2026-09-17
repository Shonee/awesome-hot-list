import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from src.hotlist.channels import bing, cnblogs, hupu, pojie52


class RequestedCollectorTests(unittest.TestCase):
    def test_bing_http_fallback_recovers_trending_topics(self):
        html = b'''<div id="tobPrompt">
        <a href="/search?q=one"><span class="tob_title">\xe5\x9b\xbd\xe5\x86\x85\xe7\x83\xad\xe7\x82\xb9\xe4\xb8\x80</span></a>
        <a href="/search?q=two"><span class="tob_title">\xe5\x9b\xbd\xe5\x86\x85\xe7\x83\xad\xe7\x82\xb9\xe4\xba\x8c</span></a>
        <a href="/search?q=three"><span class="tob_title">\xe5\x9b\xbd\xe5\x86\x85\xe7\x83\xad\xe7\x82\xb9\xe4\xb8\x89</span></a>
        </div>'''
        with patch.object(bing, "get", return_value="<html>blocked</html>"), patch("src.hotlist.channels.bing.subprocess.run", return_value=CompletedProcess([], 0, stdout=html)) as fallback:
            result = bing.collect()

        self.assertEqual(result.rankings[0].items[0].title, "国内热点一")
        self.assertEqual(result.rankings[0].ranking_id, "domestic-trending")
        fallback.assert_called_once()
        self.assertFalse(fallback.call_args.kwargs.get("shell", False))

    def test_bing_returns_disabled_when_no_valid_items(self):
        with patch.object(bing, "get", return_value="<html>blocked</html>"), patch("src.hotlist.channels.bing.subprocess.run", return_value=CompletedProcess([], 0, stdout=b"<html></html>")):
            result = bing.collect()

        self.assertEqual(result.status, "disabled")
        self.assertEqual(result.rankings, [])
        self.assertIn("仅返回 0 条有效数据", result.error)

    def test_hupu_first_ranking_is_clickable_home_posts(self):
        def source(url, **_):
            if url == hupu.HOME_URL:
                return '<a class="news-item" href="/bbs/123"><span class="news-item-info-title">首页文章</span></a>'
            return '<div class="t-info"><a href="/456.html"><span class="t-title">步行街</span></a></div>'

        with patch.object(hupu, "get", side_effect=source):
            result = hupu.collect()

        self.assertEqual([rank.name for rank in result.rankings], ["虎扑首页", "步行街热帖"])
        self.assertEqual(result.rankings[0].items[0].url, "https://m.hupu.com/bbs/123")

    def test_cnblogs_secondary_failure_does_not_discard_home_posts(self):
        def source(url, **_):
            if url == cnblogs.SOURCE_URL:
                return '<div id="post_list"><article class="post-item"><a class="post-item-title" href="/a/p/123">首页文章</a></article></div>'
            raise TimeoutError(url)

        with patch.object(cnblogs, "get", side_effect=source):
            result = cnblogs.collect()

        self.assertEqual([rank.name for rank in result.rankings], ["最新帖子"])
        self.assertEqual(result.warnings, ["精华帖子", "48 小时阅读排行"])

    def test_pojie_digest_failure_keeps_popular_posts(self):
        with patch.object(pojie52, "get", side_effect=[
            '<a class="xst" href="thread-123-1-1.html">人气热门</a>',
            TimeoutError("challenge"),
        ]), patch.object(pojie52.subprocess, "run", return_value=CompletedProcess([], 0, stdout=b"<html></html>")):
            result = pojie52.collect()

        self.assertEqual([rank.name for rank in result.rankings], ["人气热门"])
        self.assertEqual(result.warnings, ["精华采撷"])

    def test_pojie_empty_popular_ranking_is_reported_when_digest_succeeds(self):
        with patch.object(pojie52, "get", side_effect=[
            "<html><body>verification required</body></html>",
            '<a class="xst" href="thread-456-1-1.html">精华文章</a>',
        ]), patch.object(pojie52.subprocess, "run", return_value=CompletedProcess([], 0, stdout=b"<html></html>")):
            result = pojie52.collect()

        self.assertEqual([rank.name for rank in result.rankings], ["人气热门", "精华采撷"])
        self.assertEqual(len(result.rankings[0].items), 0)
        self.assertEqual(len(result.rankings[1].items), 1)
        self.assertEqual(result.warnings, ["人气热门"])

    def test_pojie_http_fallback_recovers_hot_page_from_verification(self):
        hot_html = '<meta charset="gbk"><a class="xst" href="thread-123-1-1.html">人气热门</a>'
        with patch.object(pojie52, "get", side_effect=[
            "<html><body>verification required</body></html>",
            '<a class="xst" href="thread-456-1-1.html">精华文章</a>',
        ]), patch.object(pojie52.subprocess, "run", return_value=CompletedProcess([], 0, stdout=hot_html.encode("gbk"))) as fallback:
            result = pojie52.collect()

        self.assertEqual([len(rank.items) for rank in result.rankings], [1, 1])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.rankings[0].items[0].title, "人气热门")
        fallback.assert_called_once()
        self.assertFalse(fallback.call_args.kwargs.get("shell", False))


if __name__ == "__main__":
    unittest.main()
