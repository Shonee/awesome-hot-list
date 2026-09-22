import os
import time
import unittest
from unittest.mock import patch

import requests

from src.hotlist.channels import dailyhot, tophub
from src.utils import http_utils


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


class DailyHotRequestPolicyTests(unittest.TestCase):
    def setUp(self):
        dailyhot.reset_request_state()

    def tearDown(self):
        dailyhot.reset_request_state()

    @patch("src.hotlist.channels.dailyhot.time.sleep")
    @patch("src.hotlist.channels.dailyhot.time.monotonic", side_effect=[10.0, 11.0, 16.0])
    @patch("src.hotlist.channels.dailyhot.get", side_effect=[{"data": [1]}, {"data": [2]}])
    def test_different_endpoints_are_throttled(self, request, _clock, sleep):
        dailyhot.fetch_payload("https://api-hot.imsyy.top/one")
        dailyhot.fetch_payload("https://api-hot.imsyy.top/two")

        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(4.0)

    @patch("src.hotlist.channels.dailyhot.time.monotonic", return_value=20.0)
    @patch("src.hotlist.channels.dailyhot.get", return_value={"data": [1]})
    def test_same_endpoint_is_cached(self, request, _clock):
        self.assertEqual(
            dailyhot.fetch_payload("https://api-hot.imsyy.top/one"),
            dailyhot.fetch_payload("https://api-hot.imsyy.top/one"),
        )
        request.assert_called_once()

    @patch("src.hotlist.channels.dailyhot.time.monotonic", side_effect=[10.0, 11.0])
    @patch("src.hotlist.channels.dailyhot.get")
    def test_rate_limit_opens_cooldown(self, request, _clock):
        response = requests.Response()
        response.status_code = 429
        request.side_effect = requests.HTTPError("rate limited", response=response)

        with self.assertRaisesRegex(RuntimeError, "冷却"):
            dailyhot.fetch_payload("https://api-hot.imsyy.top/one")
        with self.assertRaisesRegex(RuntimeError, "冷却"):
            dailyhot.fetch_payload("https://api-hot.imsyy.top/two")
        request.assert_called_once()


class DomainCooldownBudgetTests(unittest.TestCase):
    URL = "https://api.example.com/hot-list"
    HOST = "api.example.com"

    def setUp(self):
        http_utils._DOMAIN_STATE.clear()
        self.addCleanup(http_utils._DOMAIN_STATE.clear)

    @patch("src.utils.http_utils.time.sleep")
    def test_cooldown_within_budget_is_still_honoured(self, sleep):
        env = {"HOTLIST_DOMAIN_MIN_INTERVAL_SECONDS": "1", "HOTLIST_DOMAIN_MAX_WAIT_SECONDS": "30"}
        with patch.dict(os.environ, env):
            http_utils._DOMAIN_STATE[self.HOST] = time.monotonic() + 5
            http_utils._domain_gate(self.URL)

        sleep.assert_called_once()
        self.assertLessEqual(sleep.call_args[0][0], 5.0)

    @patch("src.utils.http_utils.time.sleep")
    def test_cooldown_beyond_budget_fails_instead_of_sleeping(self, sleep):
        env = {"HOTLIST_DOMAIN_MIN_INTERVAL_SECONDS": "1", "HOTLIST_DOMAIN_MAX_WAIT_SECONDS": "30"}
        with patch.dict(os.environ, env):
            http_utils._DOMAIN_STATE[self.HOST] = time.monotonic() + 600
            with self.assertRaisesRegex(http_utils.DomainCooldownError, "cooling down"):
                http_utils._domain_gate(self.URL)

        sleep.assert_not_called()

    @patch("src.utils.http_utils._domain_gate", side_effect=http_utils.DomainCooldownError("cooling down"))
    def test_get_does_not_retry_a_cooling_domain(self, gate):
        with self.assertRaises(http_utils.DomainCooldownError):
            http_utils.get(self.URL, retries=3)

        gate.assert_called_once()

    @patch("src.utils.http_utils._domain_gate", side_effect=http_utils.DomainCooldownError("cooling down"))
    def test_post_does_not_retry_a_cooling_domain(self, gate):
        with self.assertRaises(http_utils.DomainCooldownError):
            http_utils.post(self.URL, {"page": 1}, retries=3)

        gate.assert_called_once()

    @patch("requests.sessions.Session.request")
    def test_retry_after_beyond_the_cap_is_clamped(self, request):
        response = requests.Response()
        response.status_code = 429
        response.headers["Retry-After"] = "3600"
        response.url = self.URL
        request.side_effect = requests.HTTPError("rate limited", response=response)

        with patch.dict(os.environ, {"HOTLIST_DOMAIN_MIN_INTERVAL_SECONDS": "1"}):
            with patch("src.utils.http_utils.time.sleep"):
                with self.assertRaises(requests.HTTPError):
                    http_utils.get(self.URL, retries=1)

        remaining = http_utils._DOMAIN_STATE[self.HOST] - time.monotonic()
        self.assertLessEqual(remaining, http_utils.DOMAIN_COOLDOWN_CAP)
        self.assertGreater(remaining, 60.0)


if __name__ == "__main__":
    unittest.main()
