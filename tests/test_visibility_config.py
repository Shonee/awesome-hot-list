import unittest
import tempfile
from unittest.mock import patch

from src.hotlist.registry import HOURLY_CHANNELS, LIVE_CHANNELS, SPECIAL_CHANNELS, get_channel, iter_channels, resolve_channels
from src.script.collect import run
from src.script.render import _channel_config


class ChannelVisibilityConfigTests(unittest.TestCase):
    def test_hidden_channels_other_than_fuliba_leave_every_default_collection_group(self):
        hidden = [channel for channel in iter_channels() if not channel.visible_by_default and channel.channel_id != "fuliba"]
        for channel in hidden:
            with self.subTest(channel=channel.channel_id):
                self.assertFalse(channel.enabled_by_default)
                for group in (None, "all", ["all"], "hourly", "special", "live"):
                    self.assertNotIn(channel.channel_id, resolve_channels(group))
        self.assertIn("fuliba", resolve_channels("all"))
        self.assertIn("fuliba", resolve_channels("hourly"))

    def test_default_all_run_only_passes_enabled_channels_to_collectors(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("src.script.collect.collect_channels", return_value=[]) as collect,
            patch("src.script.collect._write_enabled", return_value=False),
        ):
            run("all", data_root=directory)
        selected = collect.call_args.args[0]
        self.assertEqual(selected, [channel.channel_id for channel in iter_channels(enabled_only=True)])
        self.assertIn("fuliba", selected)

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

    def test_live_surfaces_are_disabled_without_hiding_regular_rankings(self):
        configs = {item["channelId"]: item for item in _channel_config()}
        for channel_id in ("sina", "cls", "yicai", "wallstreetcn"):
            with self.subTest(channel=channel_id):
                self.assertIn("live", get_channel(channel_id).disabled_surfaces)
                self.assertIn("live", configs[channel_id]["disabledSurfaces"])
                self.assertNotIn(channel_id, LIVE_CHANNELS)
        for channel_id in ("sina", "cls", "yicai"):
            self.assertTrue(get_channel(channel_id).enabled_by_default)
            self.assertTrue(get_channel(channel_id).visible_by_default)
            self.assertIn(channel_id, HOURLY_CHANNELS)
        self.assertFalse(get_channel("wallstreetcn").enabled_by_default)
        self.assertFalse(get_channel("wallstreetcn").visible_by_default)
        self.assertNotIn("wallstreetcn", SPECIAL_CHANNELS)


if __name__ == "__main__":
    unittest.main()
