import os
import unittest
from unittest.mock import patch

from src.hotlist.channels import tophub
from src.hotlist.channels import wechat, zhihu
from src.hotlist.models import HotItem, Ranking
from src.hotlist.registry import CHANNEL_ORDER, HOURLY_CHANNELS, get_channel


ZHIHU_TOP_SEARCH_HTML = """
<div class="TopSearchMain-item">
  <div class="TopSearchMain-title">知乎热搜</div>
</div>
"""

TOPHUB_ZHIHU_HTML = """
<table class="table"><tbody>
  <tr>
    <td align="center">1.</td>
    <td class="al"><img src="https://picx.zhimg.com/cover.png"></td>
    <td class="al">
      <div><a href="https://www.zhihu.com/question/42" itemid="42">知乎热榜问题</a></div>
      <div class="item-desc">123 万热度</div>
    </td>
    <td><a href="https://www.zhihu.com/question/42" title="查看详细">详情</a></td>
  </tr>
  <tr><td>2.</td><td><a href="https://example.com/not-allowed">无关链接</a></td></tr>
</tbody></table>
"""

TOPHUB_WECHAT_HTML = """
<table class="table"><tbody>
  <tr>
    <td align="center">1.</td>
    <td><a href="https://mp.weixin.qq.com/s?__biz=demo&amp;mid=1" itemid="1">微信热文</a></td>
    <td class="ws">10.0万</td>
    <td><a href="https://mp.weixin.qq.com/s?__biz=demo&amp;mid=1" title="查看详细">详情</a></td>
  </tr>
</tbody></table>
"""


class TophubProviderTests(unittest.TestCase):
    def test_parse_table_filters_hosts_and_duplicate_detail_links(self):
        items = tophub.parse_ranking(TOPHUB_ZHIHU_HTML, allowed_hosts=("www.zhihu.com",))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].rank, 1)
        self.assertEqual(items[0].title, "知乎热榜问题")
        self.assertEqual(items[0].hot, "123 万热度")
        self.assertEqual(items[0].image_url, "https://picx.zhimg.com/cover.png")

    def test_parse_table_supports_wechat_hot_value(self):
        items = tophub.parse_ranking(TOPHUB_WECHAT_HTML, allowed_hosts=("mp.weixin.qq.com",))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "微信热文")
        self.assertEqual(items[0].hot, "10.0万")
        self.assertIn("&mid=1", items[0].url)

    @patch("src.hotlist.channels.tophub.get", return_value=TOPHUB_ZHIHU_HTML)
    def test_fetch_ranking_rejects_broken_partial_page(self, request):
        with self.assertRaises(RuntimeError):
            tophub.fetch_ranking(
                "https://tophub.today/n/demo",
                allowed_hosts=("www.zhihu.com",),
                min_items=2,
            )

        request.assert_called_once()


class ZhihuFallbackTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("src.hotlist.channels.zhihu.fetch_tophub_ranking")
    @patch("src.hotlist.channels.zhihu.get", return_value=ZHIHU_TOP_SEARCH_HTML)
    def test_missing_cookie_uses_official_search_and_tophub_hot(self, request, fallback):
        fallback.return_value = [HotItem(1, "降级热榜", "https://www.zhihu.com/question/1")]

        result = zhihu.collect()

        self.assertEqual([ranking.ranking_id for ranking in result.rankings], ["search", "hot"])
        self.assertEqual(result.rankings[1].provider_name, "今日热榜")
        self.assertEqual(result.rankings[1].source_url, zhihu.HOT_PAGE_URL)
        fallback.assert_called_once()
        request.assert_called_once_with(zhihu.SEARCH_URL, headers=zhihu._headers())

    @patch.dict(os.environ, {"ZHIHU_COOKIE": "z_c0=demo"}, clear=True)
    @patch("src.hotlist.channels.zhihu.fetch_tophub_ranking")
    @patch("src.hotlist.channels.zhihu.get")
    def test_cookie_prefers_official_hot_api(self, request, fallback):
        request.side_effect = [
            ZHIHU_TOP_SEARCH_HTML,
            {"data": [{"target": {"id": 42, "title": "官方热榜", "created": 1788523206}}]},
        ]

        result = zhihu.collect()

        self.assertEqual(result.rankings[1].items[0].title, "官方热榜")
        self.assertEqual(result.rankings[1].provider_name, "知乎官方")
        fallback.assert_not_called()

    @patch.dict(os.environ, {"ZHIHU_COOKIE": "expired"}, clear=True)
    @patch("src.hotlist.channels.zhihu.fetch_tophub_ranking")
    @patch("src.hotlist.channels.zhihu.get")
    def test_invalid_cookie_falls_back_to_tophub(self, request, fallback):
        request.side_effect = [ZHIHU_TOP_SEARCH_HTML, RuntimeError("401 unauthorized")]
        fallback.return_value = [HotItem(1, "降级热榜", "https://www.zhihu.com/question/1")]

        result = zhihu.collect()

        self.assertEqual(result.rankings[1].provider_name, "今日热榜")
        fallback.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.hotlist.channels.zhihu.fetch_tophub_ranking", side_effect=RuntimeError("down"))
    @patch("src.hotlist.channels.zhihu.get", return_value=ZHIHU_TOP_SEARCH_HTML)
    def test_hot_list_failure_is_not_hidden_by_search_results(self, _request, _fallback):
        with self.assertRaises(RuntimeError):
            zhihu.collect()


class WechatCollectorTests(unittest.TestCase):
    @patch("src.hotlist.channels.wechat.fetch_tophub_ranking")
    def test_wechat_returns_channel_snapshot(self, fallback):
        fallback.return_value = [HotItem(1, "微信热文", "https://mp.weixin.qq.com/s/demo")]

        result = wechat.collect()

        self.assertEqual(result.channel_id, "wechat")
        self.assertEqual(result.rankings[0].ranking_id, "articles_24h")
        self.assertEqual(result.rankings[0].provider_name, "今日热榜")
        self.assertEqual(result.rankings[0].source_url, wechat.TOPHUB_WECHAT_URL)


class FallbackRegistryTests(unittest.TestCase):
    def test_zhihu_is_hourly_and_cookie_is_optional(self):
        definition = get_channel("zhihu")

        self.assertTrue(definition.enabled_by_default)
        self.assertEqual(definition.requires_env, ())
        self.assertEqual(definition.frequency_minutes, 60)
        self.assertIn("zhihu", HOURLY_CHANNELS)

    def test_wechat_is_registered_before_rss(self):
        self.assertIn("wechat", HOURLY_CHANNELS)
        self.assertLess(CHANNEL_ORDER.index("wechat"), CHANNEL_ORDER.index("rss"))


class RankingProviderMetadataTests(unittest.TestCase):
    def test_provider_metadata_is_optional_and_serialized(self):
        ranking = Ranking(
            "hot",
            "热榜",
            provider_name="今日热榜",
            provider_url="https://tophub.today/n/demo",
        )

        payload = ranking.to_dict()

        self.assertEqual(payload["providerName"], "今日热榜")
        self.assertEqual(payload["providerUrl"], "https://tophub.today/n/demo")


if __name__ == "__main__":
    unittest.main()
