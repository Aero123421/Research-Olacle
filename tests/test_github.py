from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.campaign import create_campaign, finalize_campaign_contract
from codex_research_harness.github import GitHubClient, campaign_project_values
from tests.helpers import make_repo, write_ready_contract


class GitHubClientTests(unittest.TestCase):
    def test_dry_run_setup_and_campaign_sync_are_complete_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            client = GitHubClient(paths, dry_run=True)
            setup = client.setup_project()
            self.assertEqual(setup["project_number"], 1)
            self.assertTrue(setup["seed_issues"])
            self.assertTrue((paths.local / "github.json").exists())

            create_campaign(paths, title="Explore", goal="Find robust evidence")
            write_ready_contract(paths)
            finalize_campaign_contract(paths, "C-001")
            first = client.sync_campaign("C-001")
            second = client.sync_campaign("C-001")
            self.assertEqual(first["issue"]["number"], second["issue"]["number"])
            self.assertTrue(first["project_item_id"])
            self.assertTrue((paths.campaigns / "C-001" / "GITHUB_SYNC.json").exists())
            self.assertTrue(any(command[1:3] == ["project", "item-edit"] for command in client.commands))

    def test_campaign_field_mapping(self) -> None:
        values = campaign_project_values(
            {
                "budget": {"gpu_hours": 8},
                "owner": {"runtime": "codex-goal", "model": "gpt-5.6-sol", "effort": "high"},
            },
            {
                "status": "executing",
                "phase": "full_cv",
                "health": "on_track",
                "research_signal": "promising",
                "current_action": "Fold 3 of 5",
                "next_actions": ["Confirm on another seed"],
                "resources": {"gpu_hours_used": 3.5},
                "forecast": {"finish_high": "2026-07-15T22:00:00+09:00"},
            },
        )
        self.assertEqual(values["Status"], "Executing")
        self.assertEqual(values["Phase"], "Full CV")
        self.assertEqual(values["GPU Planned h"], 8.0)
        self.assertEqual(values["GPU Actual h"], 3.5)
        self.assertEqual(values["Research Signal"], "Promising")


if __name__ == "__main__":
    unittest.main()
