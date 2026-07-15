from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.selftest import run_self_test
from tests.helpers import make_repo


class SelfTestTests(unittest.TestCase):
    def test_full_repository_passes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = run_self_test(
            __import__("codex_research_harness.models", fromlist=["LabPaths"]).LabPaths(root)
        )
        self.assertTrue(result["ok"], result)
        self.assertGreaterEqual(result["skill_count"], 12)

    def test_missing_required_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            # make_repo intentionally copies only the smaller test fixture; the
            # production self-test must report the missing adapters/config.
            result = run_self_test(paths)
            self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
