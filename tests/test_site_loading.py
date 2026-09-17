import shutil
import subprocess
import unittest
from pathlib import Path


SITE = Path(__file__).resolve().parents[1] / "src/template/site.html"
ROOT = SITE.parents[2]


class SiteLoadingTests(unittest.TestCase):
    def test_latest_is_not_gated_on_reports_and_reports_load_on_navigation(self):
        source = SITE.read_text(encoding="utf-8")
        self.assertIn("function loadSiteData() {\n      loadLatest();\n    }", source)
        self.assertIn("if (name === 'today') loadTodayReport();", source)
        self.assertIn("if (name === 'history') loadHistoryReport();", source)
        self.assertIn("controller.abort()", source)

    def test_report_dialog_deduplicates_historical_payloads(self):
        source = SITE.read_text(encoding="utf-8")
        self.assertIn("const seen = new Map();", source)
        self.assertIn("function normalizeHits(hits)", source)
        self.assertIn("function groupHits(hits)", source)
        self.assertIn("similarTitle(title, previous)", source)

    def test_noncritical_surfaces_load_after_hotlist(self):
        source = SITE.read_text(encoding="utf-8")

        self.assertIn("const SURFACE_DATA_FILES", source)
        self.assertIn("'./data/live.json'", source)
        self.assertIn("'./data/digest.json'", source)
        self.assertIn("'./data/authority.json'", source)
        self.assertIn("scheduleSupplementaryLoad", source)
        self.assertIn("Promise.allSettled", source)
        self.assertLess(source.index("await fetchJson('./data/latest.json'"), source.index("scheduleSupplementaryLoad"))

    def test_channel_cards_use_dom_budget_and_progressive_mounting(self):
        source = SITE.read_text(encoding="utf-8")

        self.assertIn("const INITIAL_DOM_BUDGET = 1500;", source)
        self.assertIn("new IntersectionObserver", source)
        self.assertIn("requestIdleCallback", source)
        self.assertIn("data-lazy-channel", source)
        self.assertIn("projectedNodeCount", source)
        self.assertIn("respectBudget: true", source)
        self.assertIn("releaseInitialDomBudget", source)
        self.assertNotIn("keys.map(channelCard).join('')", source)

    @unittest.skipUnless(shutil.which("node"), "Node.js is unavailable")
    def test_report_ui_behavior(self):
        result = subprocess.run(
            ["node", "--test", "tests/test_site_report_ui.mjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
