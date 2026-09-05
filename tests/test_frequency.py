import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.hotlist.registry import SPECIAL_CHANNELS
from src.hotlist.runner import due_channel_ids


class FrequencyTests(unittest.TestCase):
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
            self.assertTrue(set(SPECIAL_CHANNELS) >= {"github", "v2ex"})


if __name__ == "__main__":
    unittest.main()
