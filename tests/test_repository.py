from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from codex_research_harness.models import LabPaths
from codex_research_harness.repository import RepositoryAdoptionError, adopt_repository


class RepositoryAdoptionTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)

    def test_clean_template_clone_can_generate_idempotent_adoption_plan(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "repo"
            root.mkdir()
            self._git(root, "init", "-b", "main")
            self._git(root, "config", "user.email", "test@example.invalid")
            self._git(root, "config", "user.name", "Harness Test")
            (root / "README.md").write_text("template\n", encoding="utf-8")
            self._git(root, "add", "README.md")
            self._git(root, "commit", "-m", "template")
            self._git(root, "remote", "add", "origin", "https://github.com/example/template.git")

            result = adopt_repository(
                LabPaths(root),
                name_with_owner="example/private-research",
                visibility="private",
                dry_run=True,
            )
            self.assertEqual(result["repository"], "example/private-research")
            self.assertEqual(result["template_upstream"], "https://github.com/example/template.git")
            self.assertIn(["git", "remote", "rename", "origin", "template-upstream"], result["commands"])
            self.assertIn("--push", result["commands"][-1])

    def test_dirty_tree_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "repo"
            root.mkdir()
            self._git(root, "init", "-b", "main")
            (root / "uncommitted.txt").write_text("dirty", encoding="utf-8")
            with self.assertRaises(RepositoryAdoptionError):
                adopt_repository(
                    LabPaths(root),
                    name_with_owner="example/private-research",
                    dry_run=True,
                )


if __name__ == "__main__":
    unittest.main()
