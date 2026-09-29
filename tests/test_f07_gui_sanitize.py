"""F-07: GUI must sanitize model HTML before innerHTML insertion."""
from __future__ import annotations

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestF07GuiSanitize(unittest.TestCase):
    def test_dompurify_loaded_and_used(self):
        index = open(os.path.join(ROOT, "gui", "index.html"), encoding="utf-8").read()
        app = open(os.path.join(ROOT, "gui", "app.js"), encoding="utf-8").read()
        self.assertIn("dompurify", index.lower())
        self.assertIn("sanitizeMarkdownHtml", app)
        self.assertIn("DOMPurify.sanitize", app)
        # Avatar markdown path must go through sanitize, not raw marked.parse into innerHTML.
        self.assertRegex(
            app,
            re.compile(r"sanitizeMarkdownHtml\s*\(\s*marked\.parse", re.M),
        )
        self.assertIn("escapeHtml(String(filename", app)
        self.assertIn("escapeHtml(String(proj))", app)


if __name__ == "__main__":
    unittest.main()
