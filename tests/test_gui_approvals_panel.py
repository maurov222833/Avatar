"""GUI approvals panel residual of F-18 (markup + JS handlers present)."""
from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestGuiApprovalsPanel(unittest.TestCase):
    def test_index_has_approvals_section(self):
        html = open(os.path.join(ROOT, "gui", "index.html"), encoding="utf-8").read()
        self.assertIn('id="approvals-list"', html)
        self.assertIn('id="approvals-badge"', html)
        self.assertIn('id="approvals-header-badge"', html)

    def test_app_js_polls_and_resolves(self):
        js = open(os.path.join(ROOT, "gui", "app.js"), encoding="utf-8").read()
        self.assertIn("function refreshApprovalsPanel", js)
        self.assertIn("function resolveApprovalFromGui", js)
        self.assertIn('/api/approvals/pending', js)
        self.assertIn("/api/approvals/${encodeURIComponent(approvalId)}/resolve", js)
        self.assertIn("setInterval(refreshApprovalsPanel", js)
        self.assertIn('resolver: "gui"', js)


if __name__ == "__main__":
    unittest.main()
