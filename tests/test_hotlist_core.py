import json
import os
import tempfile
import unittest

from src.hotlist.models import ChannelSnapshot, HotItem, Ranking
from src.hotlist.registry import CHANNEL_ORDER, ChannelDefinition, resolve_channels
from src.hotlist.runner import collect_channels, merge_latest_snapshot


class HotlistModelTests(unittest.TestCase):
    def test_snapshot_supports_multiple_rankings(self):
        snapshot = ChannelSnapshot(
            channel_id="bilibili",
            channel_name="哔哩哔哩",
            source_url="https://www.bilibili.com/v/popular/all",
            fetched_at="2026-09-04 10:00:00",
            rankings=[
                Ranking(
                    ranking_id="popular",
                    name="全站热门",
                    items=[HotItem(rank=1, title="示例视频", url="https://b23.tv/example", hot=123)],
                ),
                Ranking(ranking_id="search", name="热门搜索", items=[]),
            ],
        )

        payload = snapshot.to_dict()

        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["channelId"], "bilibili")
        self.assertEqual([item["id"] for item in payload["rankings"]], ["popular", "search"])
        self.assertEqual(payload["rankings"][0]["items"][0]["hot"], 123)

    def test_legacy_rows_keep_ranking_name_and_fetch_time(self):
        snapshot = ChannelSnapshot(
            channel_id="demo",
            channel_name="示例",
            source_url="https://example.com",
            fetched_at="2026-09-04 11:30:00",
            rankings=[
                Ranking(
                    ranking_id="hot",
                    name="热榜",
                    items=[HotItem(rank=1, title="热点", url="https://example.com/hot")],
                )
            ],
        )

        self.assertEqual(
            snapshot.to_legacy_rows(),
            [
                {
                    "index": 1,
                    "title": "热点",
                    "desc": "",
                    "hot": "",
                    "url": "https://example.com/hot",
                    "image": "",
                    "source": "示例",
                    "type": "热榜",
                    "datetime": "2026-09-04 11:30:00",
                }
            ],
        )


class RegistryTests(unittest.TestCase):
    def test_default_order_matches_the_product_configuration(self):
        self.assertEqual(
            CHANNEL_ORDER,
            (
                "bilibili", "douyin", "weibo", "zhihu", "github",
                "juejin", "toutiao", "acfun", "ithome", "douban", "hupu",
                "36kr", "tonghuashun", "maimai", "xueqiu", "v2ex",
                "stackoverflow", "cls", "rss",
            ),
        )

    def test_hupu_is_enabled_by_default_after_mobile_ssr_adapter(self):
        from src.hotlist.registry import get_channel

        self.assertTrue(get_channel("hupu").enabled_by_default)

    def test_resolve_channels_accepts_all_or_comma_separated_ids(self):
        self.assertEqual(resolve_channels("bilibili,douyin"), ["bilibili", "douyin"])
        self.assertEqual(resolve_channels("all"), list(CHANNEL_ORDER))
        with self.assertRaises(ValueError):
            resolve_channels("unknown")


class RunnerTests(unittest.TestCase):
    def test_one_channel_failure_does_not_hide_successful_channels(self):
        def successful():
            return ChannelSnapshot(
                channel_id="ok",
                channel_name="正常渠道",
                source_url="https://example.com/ok",
                fetched_at="2026-09-04 10:00:00",
                rankings=[Ranking("hot", "热榜", [HotItem(1, "热点", "https://example.com/1")])],
            )

        def failed():
            raise RuntimeError("temporary failure")

        definitions = {
            "ok": ChannelDefinition("ok", "正常渠道", 1, "OK", "#111111", successful),
            "bad": ChannelDefinition("bad", "异常渠道", 2, "BAD", "#222222", failed),
        }

        snapshots = collect_channels(["ok", "bad"], definitions=definitions)

        self.assertEqual([item.status for item in snapshots], ["ok", "error"])
        self.assertIn("temporary failure", snapshots[1].error)

    def test_latest_snapshot_merge_preserves_other_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "latest.json")
            with open(output, "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "schemaVersion": 1,
                        "generatedAt": "old",
                        "channels": [{"channelId": "kept", "status": "ok"}],
                    },
                    file,
                )

            incoming = ChannelSnapshot(
                channel_id="fresh",
                channel_name="新渠道",
                source_url="https://example.com/fresh",
                fetched_at="2026-09-04 12:00:00",
                rankings=[],
            )
            merge_latest_snapshot([incoming], output, channel_order=("fresh", "kept"))

            with open(output, "r", encoding="utf-8") as file:
                payload = json.load(file)

            self.assertEqual([item["channelId"] for item in payload["channels"]], ["fresh", "kept"])
            self.assertEqual(payload["channels"][0]["channelName"], "新渠道")

    def test_failed_refresh_keeps_last_successful_rankings(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "latest.json")
            previous = ChannelSnapshot(
                channel_id="demo",
                channel_name="示例",
                source_url="https://example.com",
                fetched_at="2026-09-04 10:00:00",
                rankings=[Ranking("hot", "热榜", [HotItem(1, "旧数据", "https://example.com/1")])],
            ).to_dict()
            with open(output, "w", encoding="utf-8") as file:
                json.dump({"channels": [previous]}, file)

            failed = ChannelSnapshot.unavailable(
                "demo",
                "示例",
                "https://example.com",
                "2026-09-04 11:00:00",
                "error",
                "network down",
            )
            merge_latest_snapshot([failed], output, channel_order=("demo",))

            with open(output, "r", encoding="utf-8") as file:
                channel = json.load(file)["channels"][0]

            self.assertEqual(channel["status"], "stale")
            self.assertEqual(channel["fetchedAt"], "2026-09-04 10:00:00")
            self.assertEqual(channel["rankings"][0]["items"][0]["title"], "旧数据")
            self.assertEqual(channel["checkedAt"], "2026-09-04 11:00:00")


if __name__ == "__main__":
    unittest.main()
