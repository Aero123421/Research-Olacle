from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_research_harness.bootstrap import initialize_repository
from codex_research_harness.doctor import run_doctor
from codex_research_harness.models import LabPaths
from codex_research_harness.repository import RepositoryAdoptionError, adopt_repository


class RepositoryAdoptionTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)

    def _clean_repo(self, raw: str) -> tuple[Path, LabPaths]:
        root = Path(raw) / "repo"
        root.mkdir()
        self._git(root, "init", "-b", "main")
        self._git(root, "config", "user.email", "test@example.invalid")
        self._git(root, "config", "user.name", "Harness Test")
        (root / ".gitignore").write_text(".research-lab/local/\nruntime/*\n", encoding="utf-8")
        (root / "TEMPLATE_VERSION").write_text("0.1.0\n", encoding="utf-8")
        (root / "README.md").write_text("template\n", encoding="utf-8")
        self._git(root, "add", ".")
        self._git(root, "commit", "-m", "template")
        self._git(root, "remote", "add", "origin", "https://github.com/example/template.git")
        paths = LabPaths(root)
        paths.ensure_runtime()
        return root, paths

    def _fake_gh(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        helper = directory / "fake_gh.py"
        helper.write_text(
            """from __future__ import annotations
import subprocess
import sys

if sys.argv[1:3] != ["repo", "create"] or len(sys.argv) < 4:
    raise SystemExit(2)
repository = sys.argv[3]
subprocess.run(
    ["git", "remote", "add", "origin", f"https://github.com/{repository}.git"],
    check=True,
)
print(f"created {repository}")
""",
            encoding="utf-8",
        )
        if os.name == "nt":
            launcher = directory / "gh.cmd"
            launcher.write_text(f'@echo off\r\npython "{helper}" %*\r\n', encoding="utf-8")
        else:
            launcher = directory / "gh"
            launcher.write_text(f'#!/usr/bin/env sh\nexec python3 "{helper}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        return directory

    def test_local_init_keeps_template_clone_clean_for_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root, paths = self._clean_repo(raw)
            initialize_repository(
                paths,
                answers={"browser": {"mode": "built_in", "chrome_profile": None}},
            )
            run_doctor(paths, profile="quick")
            status = self._git(root, "status", "--porcelain", "--untracked-files=all").stdout.strip()
            self.assertEqual(status, "")

            result = adopt_repository(
                paths,
                name_with_owner="example/private-research",
                visibility="private",
                dry_run=True,
            )
            self.assertEqual(result["repository"], "example/private-research")
            self.assertEqual(result["template_upstream"], "https://github.com/example/template.git")
            self.assertIn(["git", "remote", "rename", "origin", "template-upstream"], result["commands"])
            self.assertIn("--push", result["commands"][-1])

    def test_successful_adoption_materializes_setup_only_in_new_repository(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root, paths = self._clean_repo(raw)
            initialize_repository(
                paths,
                answers={"browser": {"mode": "built_in", "chrome_profile": None}},
            )
            run_doctor(paths, profile="quick")
            fake_bin = self._fake_gh(Path(raw) / "bin")
            with patch.dict(os.environ, {"PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}):
                result = adopt_repository(
                    paths,
                    name_with_owner="example/private-research",
                    visibility="private",
                )

            self.assertTrue(result["materialized_files"])
            self.assertEqual(
                self._git(root, "remote", "get-url", "origin").stdout.strip(),
                "https://github.com/example/private-research.git",
            )
            self.assertEqual(
                self._git(root, "remote", "get-url", "template-upstream").stdout.strip(),
                "https://github.com/example/template.git",
            )
            self.assertTrue((root / "research/setup/AGENT_ROSTER.md").exists())
            self.assertTrue((root / "research/human/PROFILE.json").exists())

    def test_dirty_tree_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root, paths = self._clean_repo(raw)
            (root / "uncommitted.txt").write_text("dirty", encoding="utf-8")
            with self.assertRaises(RepositoryAdoptionError):
                adopt_repository(
                    paths,
                    name_with_owner="example/private-research",
                    dry_run=True,
                )


if __name__ == "__main__":
    unittest.main()
