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
            with (
                patch("src.script.collect.collect_channels", return_value=[snapshot]),
                patch("src.script.collect.build_report", return_value={"date": "2026-09-06"}),
            ):
                run("douyin", data_root=str(root))

            self.assertTrue((root / "archived/douyin/2026/09/csv/2026-09-06.csv").is_file())
            self.assertTrue((root / "site/data/latest.json").is_file())
            self.assertTrue((root / "site/data/reports/today.json").is_file())

    def test_render_writes_site_to_the_selected_data_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch("src.script.render.current_date", return_value="2026-09-06"),
                patch("src.script.render.yesterday_date", return_value="2026-09-05"),
                patch("src.script.render.load_rows", return_value={}),
                patch(
                    "src.script.render.build_report",
                    side_effect=lambda date: {"date": date, "metrics": {"deduplicated": 0}},
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

    def test_bootstrap_workflow_exists(self):
        content = Path(".github/workflows/bootstrap-data-pages.yml").read_text(encoding="utf-8")
        self.assertIn("git switch --orphan data-pages", content)
        self.assertIn("git rm -rf --ignore-unmatch .", content)
        self.assertIn("src/script/render.py", content)
        self.assertNotIn("cleanup_master", content)


if __name__ == "__main__":
    unittest.main()
