import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.hotlist.models import ChannelSnapshot, HotItem, Ranking
from src.script.collect import run
from src.script.render import main as render_site


class DataRootTests(unittest.TestCase):
    def test_collect_writes_only_under_the_selected_data_root(self):
        snapshot = ChannelSnapshot(
            channel_id="douyin",
            channel_name="抖音",
            source_url="https://example.com/douyin",
            fetched_at="2026-09-06 12:00:00",
            rankings=[Ranking("hot", "热搜", [HotItem(1, "测试热点", "https://example.com/1")])],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("src.script.collect.collect_channels", return_value=[snapshot]):
                run("douyin", data_root=str(root))

            self.assertTrue((root / "archived/douyin/2026/09/csv/2026-09-06.csv").is_file())
            self.assertTrue((root / "site/data/latest.json").is_file())
            self.assertFalse((root / "site/data/reports/today.json").exists())
            for name in ("live.json", "digest.json", "authority.json"):
                self.assertTrue((root / "site/data" / name).is_file())

    def test_render_writes_site_to_the_selected_data_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch("src.script.render.current_date", return_value="2026-09-06"),
                patch("src.script.render.yesterday_date", return_value="2026-09-05"),
                patch("src.script.render.load_rows", return_value={}),
                patch(
                    "src.script.render.build_report_from_rows",
                    side_effect=lambda date, _rows: {
                        "date": date,
                        "metrics": {"deduplicated": 0},
                        "topTopics": [],
                    },
                ),
            ):
                render_site(data_root=str(root))

            self.assertTrue((root / "site/index.html").is_file())
            self.assertTrue((root / "site/data/latest.json").is_file())
            self.assertTrue((root / "site/data/reports/2026-09-05.json").is_file())
            rendered = (root / "site/index.html").read_text(encoding="utf-8")
            self.assertNotIn("__HOTLIST_CHANNEL_CONFIG__", rendered)
            self.assertIn('"channelId": "tieba"', rendered)
            self.assertIn("https://github.com/Shonee/awesome-hot-list", rendered)

    def test_render_reads_and_builds_each_comparison_date_once(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("src.script.render.current_date", return_value="2026-09-06"),
                patch("src.script.render.yesterday_date", return_value="2026-09-05"),
                patch("src.script.render.load_rows", return_value={}) as load,
                patch(
                    "src.script.render.build_report_from_rows",
                    side_effect=lambda date, _rows: {
                        "date": date,
                        "metrics": {"deduplicated": 0},
                        "topTopics": [],
                    },
                ) as build,
            ):
                render_site(data_root=directory)

        self.assertEqual([call.args[0] for call in load.call_args_list], [
            "2026-09-06", "2026-09-05", "2026-09-04",
        ])
        self.assertEqual([call.args[0] for call in build.call_args_list], [
            "2026-09-06", "2026-09-05", "2026-09-04",
        ])

    def test_rendered_site_opens_latest_hotlists_first(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        latest_nav = '<button class="nav-btn active" data-view-target="latest">最新热榜</button>'
        today_nav = '<button class="nav-btn" data-view-target="today">今日报告</button>'
        self.assertIn(latest_nav, template)
        self.assertIn(today_nav, template)
        self.assertLess(template.index(latest_nav), template.index(today_nav))
        self.assertIn('<section class="view active" id="view-latest">', template)
        self.assertIn('<section class="view" id="view-today">', template)

    def test_mobile_hotlists_show_ten_rows_without_nested_scrolling(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        self.assertIn("const MOBILE_TOP_COUNT = 10;", template)
        self.assertIn("const effectiveTopCount = isMobileViewport() ? MOBILE_TOP_COUNT : prefs.topCount;", template)
        self.assertIn("const rows = allRows.slice(0, isLive ? 100 : effectiveTopCount);", template)
        self.assertIn("const marker = isLive ? publishedLabel(item.publishedAt).slice(11, 16)", template)
        self.assertIn(".layout-channel-tabs .channel-body {", template)
        self.assertIn("overflow-y: visible;", template)
        self.assertIn(".main-nav { margin: 0 -16px; padding: 4px 16px 8px; min-width: 0; width: auto; }", template)
        self.assertIn(".nav-btn { flex: 1 1 0; min-width: 0; padding: 0 8px; }", template)

    def test_channel_defaults_and_provider_metadata_are_rendered(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        self.assertIn("const PREFS_SCHEMA_VERSION = 3;", template)
        self.assertIn("channel.visibleByDefault !== false", template)
        self.assertIn("CHANNEL_RANKING_PROVIDERS", template)
        self.assertIn("CHANNEL_RANKING_SURFACES", template)
        self.assertIn("rankingSurfaces[ranking.name] = ranking.surface || 'hotlist';", template)
        self.assertIn("providerName", template)

    def test_latest_snapshot_uses_default_cache_and_only_manual_retry_forces_reload(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        self.assertIn("async function fetchJson(path, forceRefresh = false)", template)
        self.assertIn("if (forceRefresh) options.cache = 'reload';", template)
        self.assertNotIn("cache: 'no-cache'", template)
        self.assertIn("async function loadLatest(forceRefresh = false)", template)
        self.assertIn("fetchJson('./data/latest.json', forceRefresh)", template)
        self.assertIn("addEventListener('click', () => loadLatest(true))", template)

    def test_bing_stale_snapshot_expires_after_configured_window(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        self.assertIn("function snapshotIsExpired(snapshot, channel, nowMs = Date.now())", template)
        self.assertIn("channel.staleAfterHours", template)
        self.assertIn("旧快照已超过保留时限", template)
        self.assertIn("ranking.id === 'domestic-trending'", template)
        self.assertIn("历史国际版快照已停用", template)

    def test_rss_ui_is_fully_retired(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        for marker in ("RSS", "rss", "Rss"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, template)

    def test_history_report_supports_recent_date_selection_and_day_comparison(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        self.assertIn('id="historyDateSelect"', template)
        self.assertIn("./data/reports/index.json", template)
        self.assertIn("dayComparison", template)
        self.assertNotIn("scope === 'today' ? [", template)
        self.assertIn("comparison.rising", template)
        self.assertIn("comparison.falling", template)
        self.assertIn("rankMovementValue", template)

    def test_report_cards_prefer_sampling_coverage_with_legacy_fallback(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        self.assertIn("metrics.samplingCoverage ?? metrics.coverage", template)
        self.assertEqual(template.count("采样完成度"), 2)

    def test_partial_channel_warnings_are_visible_in_status_tooltips(self):
        template = Path("src/template/site.html").read_text(encoding="utf-8")

        self.assertIn("snapshot.warnings", template)
        self.assertIn("部分来源采集失败", template)


class WorkflowContractTests(unittest.TestCase):
    def test_generated_data_workflows_use_data_pages(self):
        expectations = {
            "collect-hourly.yml": ["ref: data-pages", "--data-root", "git -C runtime"],
            "collect-special.yml": ["ref: data-pages", "--data-root", "git -C runtime"],
            "render-daily.yml": ["ref: data-pages", "--data-root", "git -C runtime"],
            "archive-weekly.yml": ["ref: data-pages", "--source-commit", "--force-with-lease"],
            "pages.yml": ["ref: data-pages", "path: site"],
        }
        workflow_root = Path(".github/workflows")
        for filename, required in expectations.items():
            content = (workflow_root / filename).read_text(encoding="utf-8")
            for value in required:
                with self.subTest(workflow=filename, value=value):
                    self.assertIn(value, content)

    def test_archive_workflow_uses_workspace_absolute_paths(self):
        content = Path(".github/workflows/archive-weekly.yml").read_text(encoding="utf-8")
        self.assertIn('git -C "$GITHUB_WORKSPACE/runtime"', content)
        self.assertIn('git -C "$GITHUB_WORKSPACE/app"', content)
        self.assertIn('python "$GITHUB_WORKSPACE/app/src/script/archive.py"', content)

    def test_daily_render_uses_project_timezone(self):
        content = Path(".github/workflows/render-daily.yml").read_text(encoding="utf-8")
        self.assertIn("TZ: Asia/Shanghai", content)

    def test_collection_workflows_persist_before_health_gate(self):
        workflow_root = Path(".github/workflows")
        for filename in ("collect-hourly.yml", "collect-special.yml"):
            content = (workflow_root / filename).read_text(encoding="utf-8")
            with self.subTest(workflow=filename):
                self.assertIn("continue-on-error: true", content)
                self.assertIn("Enforce collection health", content)

    def test_live_workflow_runs_every_fifteen_minutes_without_rebuilding_reports(self):
        content = Path(".github/workflows/collect-live.yml").read_text(encoding="utf-8")

        self.assertIn('cron: "*/15 * * * *"', content)
        self.assertIn("collect.py\" live --surface live", content)
        self.assertNotIn("--skip-report", content)
        self.assertIn("git -C runtime add archived/ site/data/live.json", content)
        self.assertNotIn("site/data/reports", content)

    def test_all_collection_workflows_leave_reports_to_the_render_job(self):
        workflow_root = Path(".github/workflows")
        for filename in ("collect-hourly.yml", "collect-special.yml", "collect-live.yml"):
            content = (workflow_root / filename).read_text(encoding="utf-8")
            with self.subTest(workflow=filename):
                self.assertNotIn("site/data/reports", content)

    def test_render_runs_hourly_and_pages_deploys_live_updates(self):
        render = Path(".github/workflows/render-daily.yml").read_text(encoding="utf-8")
        pages = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")

        self.assertIn('cron: "40 * * * *"', render)
        self.assertIn("Collect live news", pages)

    def test_collection_workflows_no_longer_configure_rss(self):
        workflow_root = Path(".github/workflows")
        for filename in ("collect-hourly.yml", "collect-special.yml", "collect-live.yml"):
            content = (workflow_root / filename).read_text(encoding="utf-8")
            with self.subTest(workflow=filename):
                self.assertNotIn("HOTLIST_RSS", content)

    def test_hourly_workflow_can_manually_collect_maimai(self):
        content = Path(".github/workflows/collect-hourly.yml").read_text(encoding="utf-8")

        self.assertIn("MAIMAI_COOKIE: ${{ secrets.MAIMAI_COOKIE }}", content)

    def test_collection_workflows_expose_tophub_rate_limit(self):
        workflow_root = Path(".github/workflows")
        for filename in ("collect-hourly.yml", "collect-special.yml"):
            content = (workflow_root / filename).read_text(encoding="utf-8")
            with self.subTest(workflow=filename):
                self.assertIn("HOTLIST_TOPHUB_MIN_INTERVAL_SECONDS:", content)

    def test_collection_workflows_expose_dailyhot_rate_limit(self):
        workflow_root = Path(".github/workflows")
        for filename in ("collect-hourly.yml", "collect-special.yml"):
            content = (workflow_root / filename).read_text(encoding="utf-8")
            with self.subTest(workflow=filename):
                self.assertIn("HOTLIST_DAILYHOT_MIN_INTERVAL_SECONDS:", content)

    def test_bootstrap_workflow_exists(self):
        content = Path(".github/workflows/bootstrap-data-pages.yml").read_text(encoding="utf-8")
        self.assertIn("git switch --orphan data-pages", content)
        self.assertIn("git rm -rf --ignore-unmatch .", content)
        self.assertIn("src/script/render.py", content)
        self.assertNotIn("cleanup_master", content)


if __name__ == "__main__":
    unittest.main()
