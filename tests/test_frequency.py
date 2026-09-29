import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.hotlist.registry import CHANNEL_ORDER, CHANNELS, SPECIAL_CHANNELS
from src.hotlist.runner import due_channel_ids


class FrequencyTests(unittest.TestCase):
    def test_default_hotlists_use_half_hour_with_trend_exceptions(self):
        for channel_id in CHANNEL_ORDER:
            definition = CHANNELS[channel_id]
            if not definition.enabled_by_default or "hotlist" not in definition.surfaces:
                continue
            expected = 360 if channel_id in {"github", "huggingface"} else 30
            with self.subTest(channel=channel_id):
                self.assertEqual(definition.frequency_minutes, expected)
        self.assertEqual(CHANNELS["readhub"].frequency_minutes, 60)

    def test_special_channel_is_due_after_configured_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(
                json.dumps(
                    {
                        "channels": [
                            {"channelId": "github", "fetchedAt": "2026-09-05 00:00:00"},
                            {"channelId": "v2ex", "fetchedAt": "2026-09-05 00:00:00"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            now = datetime(2026, 9, 5, 5, 0)
            self.assertNotIn("github", due_channel_ids(["github"], str(path), now=now))
            self.assertIn("v2ex", due_channel_ids(["v2ex"], str(path), now=now))
            self.assertTrue(set(SPECIAL_CHANNELS) >= {"github", "huggingface"})

    def test_failed_snapshot_without_rankings_is_due_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(
                json.dumps({"channels": [{
                    "channelId": "github",
                    "fetchedAt": "2026-09-05 04:59:00",
                    "status": "error",
                    "rankings": [],
                }]}),
                encoding="utf-8",
            )

            self.assertIn(
                "github",
                due_channel_ids(["github"], str(path), now=datetime(2026, 9, 5, 5, 0)),
            )


if __name__ == "__main__":
    unittest.main()
