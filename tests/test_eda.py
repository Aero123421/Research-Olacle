from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.eda import profile_dataset


class EdaTests(unittest.TestCase):
    def test_csv_profile(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "train.csv"
            source.write_text("id,x,label\n1,1.0,a\n2,,b\n2,3.0,b\n", encoding="utf-8")
            json_path, md_path = profile_dataset(source, output_dir=root / "out")
            self.assertTrue(json_path.exists())
            self.assertIn("Data inventory", md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
