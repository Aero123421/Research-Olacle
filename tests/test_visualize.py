from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.campaign import create_campaign
from codex_research_harness.visualize import generate_all
from tests.helpers import make_repo


class VisualizeTests(unittest.TestCase):
    def test_outputs_exist(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(paths, title="Test", goal="Find evidence")
            outputs = generate_all(paths)
            self.assertEqual(len(outputs), 4)
            self.assertTrue(all(path.exists() for path in outputs))


if __name__ == "__main__":
    unittest.main()
