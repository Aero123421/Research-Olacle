from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.campaign import (
    activate_campaign,
    complete_campaign,
    create_campaign,
    finalize_campaign_contract,
    update_campaign_state,
)
from codex_research_harness.schema import ValidationError
from codex_research_harness.utils import atomic_write_text, read_json
from tests.helpers import make_repo, valid_handoff, write_ready_contract


class CampaignTests(unittest.TestCase):
    def test_draft_cannot_activate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(paths, title="Explore", goal="Find evidence")
            with self.assertRaises(ValidationError):
                activate_campaign(paths, "C-001")

    def test_campaign_lifecycle_and_budget_gates(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            directory = create_campaign(paths, title="Explore", goal="Find evidence")
            write_ready_contract(paths)
            contract = finalize_campaign_contract(paths, "C-001")
            self.assertEqual(contract["contract_status"], "ready")
            state = activate_campaign(paths, "C-001")
            self.assertEqual(state["status"], "ready")

            state = update_campaign_state(
                paths,
                "C-001",
                {
                    "status": "executing",
                    "phase": "quick",
                    "resources": {"wall_hours_used": 4.0, "gpu_hours_used": 2.0, "cost_jpy": 0},
                },
            )
            self.assertEqual(state["budget_status"], "early_review")

            evidence = paths.root / "artifacts" / "evidence.txt"
            atomic_write_text(evidence, "reproducible evidence\n")
            completed = complete_campaign(paths, "C-001", valid_handoff())
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(read_json(directory / "HANDOFF.json")["outcome"], "rejected_with_evidence")
            self.assertIn("No stable improvement", (directory / "HANDOFF.md").read_text(encoding="utf-8"))

    def test_completion_rejects_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(paths, title="Explore", goal="Find evidence")
            write_ready_contract(paths)
            finalize_campaign_contract(paths, "C-001")
            with self.assertRaises(FileNotFoundError):
                complete_campaign(paths, "C-001", valid_handoff(artifact="artifacts/missing.txt"))


if __name__ == "__main__":
    unittest.main()
