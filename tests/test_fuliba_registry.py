import unittest
from unittest.mock import patch

from src.hotlist.channels.fuliba import collect, parse_articles
from src.hotlist.registry import (
    CHANNEL_ORDER,
    HOURLY_CHANNELS,
    SPECIAL_CHANNELS,
    get_channel,
)


SAMPLE_HTML = """
<article class="excerpt excerpt-latest">
  <a class="focus" href="/demo.html"><img src="https://img.example/demo.jpg"></a>
  <header><h2><a href="/demo.html">福利吧最新文章</a></h2></header>
  <p class="note">文章摘要</p>
  <div class="meta">
    <time>2026-09-14</time>
    <a class="cat" href="/flhz/"><i>\ue60e</i>福利汇总</a>
    <a class="pc views" href="/demo.html">阅读(3683)</a>
    <a class="pc" href="/demo.html#comments">评论(12)</a>
  </div>
</article>
"""


class FulibaParserTests(unittest.TestCase):
    def test_parse_articles_reads_article_metadata(self):
        items = parse_articles(SAMPLE_HTML)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "福利吧最新文章")
        self.assertEqual(items[0].url, "https://fuliba2023.net/demo.html")
        self.assertEqual(items[0].hot, 3683)
        self.assertEqual(items[0].description, "福利汇总 · 12 条评论 · 文章摘要")
        self.assertEqual(items[0].image_url, "https://img.example/demo.jpg")
        self.assertEqual(items[0].published_at, "2026-09-14")

    @patch("src.hotlist.channels.fuliba.get", return_value=SAMPLE_HTML)
    def test_collect_marks_the_official_provider(self, mocked_get):
        result = collect()

        mocked_get.assert_called_once_with(
            "https://fuliba2023.net/", timeout=15, retries=2
        )
        self.assertEqual(result.channel_id, "fuliba")
        self.assertEqual(result.rankings[0].provider_name, "福利吧官方")
        self.assertEqual(result.rankings[0].provider_url, "https://fuliba2023.net/")


class ChannelVisibilityConfigTests(unittest.TestCase):
    def test_fuliba_is_collected_hourly_but_hidden_and_excluded_from_reports(self):
        definition = get_channel("fuliba")

        self.assertTrue(definition.enabled_by_default)
        self.assertFalse(definition.visible_by_default)
        self.assertFalse(definition.include_in_report)
        self.assertIn("fuliba", HOURLY_CHANNELS)

    def test_maimai_is_not_collected_shown_or_reported_by_default(self):
        definition = get_channel("maimai")

        self.assertFalse(definition.enabled_by_default)
        self.assertFalse(definition.visible_by_default)
        self.assertFalse(definition.include_in_report)
        self.assertNotIn("maimai", SPECIAL_CHANNELS)

    def test_linuxdo_is_not_registered_as_a_standalone_channel(self):
        self.assertNotIn("linuxdo", CHANNEL_ORDER)
        with self.assertRaises(ValueError):
            get_channel("linuxdo")


if __name__ == "__main__":
    unittest.main()
