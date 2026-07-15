from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from codex_research_harness.models import LabPaths
from codex_research_harness.probes.services import SecretHygieneProbe


class SecretHygieneTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)

    def test_scans_tracked_and_untracked_source_but_not_ignored_environments(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "repo"
            root.mkdir()
            self._git(root, "init", "-b", "main")
            self._git(root, "config", "user.email", "test@example.invalid")
            self._git(root, "config", "user.name", "Harness Test")
            (root / ".gitignore").write_text("ignored-env/\n", encoding="utf-8")
            (root / "safe.txt").write_text("safe\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-m", "safe")

            fake_secret = "sk-" + ("A" * 24)
            ignored = root / "ignored-env"
            ignored.mkdir()
            (ignored / "dependency.py").write_text(fake_secret, encoding="utf-8")

            paths = LabPaths(root)
            paths.ensure_runtime()
            clean = SecretHygieneProbe(paths, {}).run()
            self.assertEqual(clean.status, "pass")

            (root / "oops.txt").write_text(fake_secret, encoding="utf-8")
            exposed = SecretHygieneProbe(paths, {}).run()
            self.assertEqual(exposed.status, "fail")
            self.assertEqual(exposed.details["findings"][0]["path"], "oops.txt")


if __name__ == "__main__":
    unittest.main()
