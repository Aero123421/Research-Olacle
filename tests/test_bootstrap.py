from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.bootstrap import (
    initialize_repository,
    materialize_repository_configuration,
)
from codex_research_harness.utils import read_json
from tests.helpers import make_repo


class BootstrapTests(unittest.TestCase):
    def test_initial_run_waits_for_browser_choice_without_touching_tracked_setup(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            profile = paths.research / "human" / "PROFILE.json"
            if profile.exists():
                profile.unlink()
            state = initialize_repository(paths)
            self.assertEqual(state["stage"], "setup_interview")
            self.assertEqual(state["browser_mode"], "unselected")
            self.assertFalse((paths.local / "browser.toml").exists())
            self.assertFalse(profile.exists())
            self.assertFalse(state["materialized"])

    def test_resumable_initialization_materializes_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            first = initialize_repository(
                paths, answers={"browser": {"mode": "chrome", "chrome_profile": "Research"}}
            )
            second = initialize_repository(
                paths, answers={"browser": {"mode": "built_in", "chrome_profile": None}}
            )
            self.assertEqual(first["created_at"], second["created_at"])
            self.assertEqual(read_json(paths.local / "answers.json")["browser"]["mode"], "built_in")
            self.assertEqual(second["stage"], "environment_discovery")
            self.assertFalse((paths.research / "human" / "PROFILE.json").exists())

            written = materialize_repository_configuration(paths)
            self.assertIn("research/setup/AGENT_ROSTER.md", written)
            self.assertTrue((paths.setup / "AGENT_ROSTER.md").exists())
            self.assertTrue((paths.research / "human" / "PROFILE.json").exists())

            final = initialize_repository(paths, materialize=True)
            self.assertTrue(final["materialized"])
            self.assertEqual(final["template_version"], "unknown")


if __name__ == "__main__":
    unittest.main()
