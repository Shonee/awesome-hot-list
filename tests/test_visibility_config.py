import unittest

from src.hotlist.registry import HOURLY_CHANNELS, LIVE_CHANNELS, SPECIAL_CHANNELS, get_channel
from src.script.render import _channel_config


class ChannelVisibilityConfigTests(unittest.TestCase):
    def test_fuliba_is_collected_but_hidden_and_excluded_from_reports(self):
        channel = get_channel("fuliba")

        self.assertTrue(channel.enabled_by_default)
        self.assertFalse(channel.visible_by_default)
        self.assertFalse(channel.include_in_report)

    def test_maimai_is_not_collected_or_visible_by_default(self):
        channel = get_channel("maimai")

        self.assertFalse(channel.enabled_by_default)
        self.assertFalse(channel.visible_by_default)

    def test_non_hotlist_sources_are_not_collected_or_visible_by_default(self):
        for channel_id in ("googletrends", "cctv", "mfa"):
            channel = get_channel(channel_id)
            with self.subTest(channel=channel_id):
                self.assertFalse(channel.enabled_by_default)
                self.assertFalse(channel.visible_by_default)
                self.assertFalse(channel.include_in_report)
                # Disabled channels must leave every scheduled collection list.
                self.assertNotIn(channel_id, HOURLY_CHANNELS)
                self.assertNotIn(channel_id, SPECIAL_CHANNELS)
                self.assertNotIn(channel_id, LIVE_CHANNELS)

    def test_rendered_channel_config_exposes_independent_flags(self):
        channels = {item["channelId"]: item for item in _channel_config()}

        self.assertFalse(channels["fuliba"]["visibleByDefault"])
        self.assertFalse(channels["fuliba"]["includeInReport"])


if __name__ == "__main__":
    unittest.main()
