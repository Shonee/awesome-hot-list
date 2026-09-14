import unittest
from unittest.mock import patch

import requests

from src.hotlist.channels import tophub


TOPHUB_HTML = """
<table class="table"><tbody>
  <tr><td>1</td><td><a href="https://example.com/one">第一条</a></td></tr>
</tbody></table>
"""


class TophubRequestPolicyTests(unittest.TestCase):
    def setUp(self):
        tophub.reset_request_state()

    def tearDown(self):
        tophub.reset_request_state()

    @patch("src.hotlist.channels.tophub.time.sleep")
    @patch("src.hotlist.channels.tophub.time.monotonic", side_effect=[10.0, 11.0, 14.0])
    @patch("src.hotlist.channels.tophub.get", return_value=TOPHUB_HTML)
    def test_different_pages_are_throttled(self, request, _clock, sleep):
        tophub.fetch_ranking("https://tophub.today/n/one", ("example.com",), min_items=1)
        tophub.fetch_ranking("https://tophub.today/n/two", ("example.com",), min_items=1)

        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(2.0)

    @patch("src.hotlist.channels.tophub.time.sleep")
    @patch("src.hotlist.channels.tophub.time.monotonic", return_value=20.0)
    @patch("src.hotlist.channels.tophub.get", return_value=TOPHUB_HTML)
    def test_same_page_is_cached_within_collection_process(self, request, _clock, sleep):
        first = tophub.fetch_ranking("https://tophub.today/n/one", ("example.com",), min_items=1)
        second = tophub.fetch_ranking("https://tophub.today/n/one", ("example.com",), min_items=1)

        self.assertEqual([item.title for item in first], ["第一条"])
        self.assertEqual([item.title for item in second], ["第一条"])
        request.assert_called_once()
        sleep.assert_not_called()

    @patch("src.hotlist.channels.tophub.time.monotonic", side_effect=[10.0, 11.0])
    @patch("src.hotlist.channels.tophub.get")
    def test_rate_limit_opens_a_batch_cooldown(self, request, _clock):
        response = requests.Response()
        response.status_code = 429
        response.headers["Retry-After"] = "120"
        request.side_effect = requests.HTTPError("rate limited", response=response)

        with self.assertRaisesRegex(RuntimeError, "冷却"):
            tophub.fetch_ranking("https://tophub.today/n/one", ("example.com",), min_items=1)
        with self.assertRaisesRegex(RuntimeError, "冷却"):
            tophub.fetch_ranking("https://tophub.today/n/two", ("example.com",), min_items=1)

        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
