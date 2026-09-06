import unittest
from unittest.mock import call, patch

import requests

from src.hotlist.channels.douyin import extract_cover_url
from src.hotlist.channels.github import collect, parse_trending
from src.utils.http_utils import post
from src.hotlist.models import HotItem


class DouyinCollectorTests(unittest.TestCase):
    def test_missing_cover_is_empty(self):
        self.assertEqual(extract_cover_url(None), "")
        self.assertEqual(extract_cover_url({}), "")
        self.assertEqual(extract_cover_url({"url_list": []}), "")

    def test_first_cover_url_is_used(self):
        self.assertEqual(
            extract_cover_url({"url_list": ["https://img.example/cover.jpg"]}),
            "https://img.example/cover.jpg",
        )


class GithubParserTests(unittest.TestCase):
    def test_semantic_trending_markup_is_normalized(self):
        html = """
        <article class="Box-row">
          <h2><a href="/owner/project">owner / project</a></h2>
          <p>A sample project.</p>
          <span itemprop="programmingLanguage">Python</span>
          <a href="/owner/project/stargazers">1,234</a>
          <a href="/owner/project/forks">56</a>
          <span class="d-inline-block float-sm-right">78 stars today</span>
        </article>
        """

        result = parse_trending(html, language="python", since="daily")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "project")
        self.assertEqual(result[0].url, "https://github.com/owner/project")
        self.assertEqual(result[0].hot, "1,234")
        self.assertIn("Python", result[0].description)

    @patch("src.hotlist.channels.github.time.sleep")
    @patch("src.hotlist.channels.github.fetch_via_search_api")
    @patch("src.hotlist.channels.github.fetch_trending", side_effect=RuntimeError("network error"))
    def test_request_failure_uses_search_fallback(self, fetch, fallback, _sleep):
        fallback.side_effect = lambda period: [HotItem(1, period, "https://example.com")]

        result = collect()

        self.assertEqual({ranking.ranking_id for ranking in result.rankings}, {"daily", "weekly", "monthly"})
        self.assertEqual(fallback.call_count, 3)
        self.assertEqual(fetch.call_count, 8)
        self.assertEqual(fetch.call_args_list.count(call("", "weekly")), 1)


class HttpRequestTests(unittest.TestCase):
    @patch("requests.post")
    def test_post_returns_json_with_shared_request_shape(self, requests_post):
        response = requests_post.return_value
        response.status_code = 200
        response.json.return_value = {"ok": True}

        result = post("https://example.com/api", payload={"page": 1}, res_type="json")

        self.assertEqual(result, {"ok": True})
        requests_post.assert_called_once()
        self.assertEqual(requests_post.call_args.kwargs["json"], {"page": 1})

    @patch("src.utils.http_utils.time.sleep")
    @patch("requests.get")
    def test_get_does_not_retry_non_retryable_client_error(self, requests_get, sleep):
        response = requests_get.return_value
        response.status_code = 403

        with self.assertRaises(requests.HTTPError):
            from src.utils.http_utils import get

            get("https://example.com/private", retries=3)

        self.assertEqual(requests_get.call_count, 1)
        sleep.assert_not_called()

    @patch("src.utils.http_utils.time.sleep")
    @patch("requests.get")
    def test_get_retries_transient_server_error(self, requests_get, sleep):
        failed = requests.Response()
        failed.status_code = 503
        failed.url = "https://example.com/api"
        success = requests.Response()
        success.status_code = 200
        success._content = b"ok"
        success.encoding = "utf-8"
        requests_get.side_effect = [failed, success]

        from src.utils.http_utils import get

        self.assertEqual(get("https://example.com/api", retries=2), "ok")
        self.assertEqual(requests_get.call_count, 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
