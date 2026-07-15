from __future__ import annotations

import re
import unittest
from pathlib import Path


class ContinuousIntegrationTests(unittest.TestCase):
    def test_third_party_actions_are_pinned_to_full_commit_shas(self) -> None:
        root = Path(__file__).resolve().parents[1]
        uses_pattern = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
        for workflow in sorted((root / ".github/workflows").glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            for action in uses_pattern.findall(text):
                if action.startswith("./"):
                    continue
                self.assertRegex(
                    action,
                    r"^[^@]+@[0-9a-f]{40}$",
                    msg=f"{workflow}: action is not pinned to a full SHA: {action}",
                )

    def test_secret_scan_uses_full_history_gitleaks(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / ".github/workflows/secret-scan.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", text)
        self.assertIn("gitleaks/gitleaks-action@", text)
        self.assertTrue((root / ".gitleaks.toml").exists())


if __name__ == "__main__":
    unittest.main()
