import unittest
from pathlib import Path


SITE = Path(__file__).resolve().parents[1] / "src/template/site.html"


class SiteLoadingTests(unittest.TestCase):
    def test_latest_is_not_gated_on_reports_and_reports_load_on_navigation(self):
        source = SITE.read_text(encoding="utf-8")
        self.assertIn("function loadSiteData() {\n      loadLatest();\n    }", source)
        self.assertIn("if (name === 'today') loadTodayReport();", source)
        self.assertIn("if (name === 'history') loadHistoryReport();", source)
        self.assertIn("controller.abort()", source)

    def test_report_dialog_deduplicates_historical_payloads(self):
        source = SITE.read_text(encoding="utf-8")
        self.assertIn("const seen = new Set();", source)
        self.assertIn("function normalizeHits(hits)", source)


if __name__ == "__main__":
    unittest.main()
