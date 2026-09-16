import unittest
from unittest.mock import patch

from src.hotlist.channels import cnblogs, hupu, pojie52


class RequestedCollectorTests(unittest.TestCase):
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
        ]):
            result = pojie52.collect()

        self.assertEqual([rank.name for rank in result.rankings], ["人气热门"])
        self.assertEqual(result.warnings, ["精华采撷"])


if __name__ == "__main__":
    unittest.main()
