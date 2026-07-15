from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.campaign import (
    activate_campaign,
    claim_executor,
    complete_campaign,
    create_campaign,
    finalize_campaign_contract,
)
from codex_research_harness.context import build_executor_context
from codex_research_harness.loop import inspect_research_loop, write_loop_state
from codex_research_harness.plans import create_research_plan, link_campaign
from codex_research_harness.utils import atomic_write_text
from tests.helpers import make_repo, valid_handoff, write_ready_contract


class ResearchLoopTests(unittest.TestCase):
    def test_state_machine_derives_planner_executor_handoff_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            self.assertEqual(inspect_research_loop(paths).action, "start_planner")

            create_research_plan(paths, user_intent="Win the competition")
            self.assertEqual(inspect_research_loop(paths).action, "run_planner")

            create_campaign(paths, title="Signal", goal="Test signal")
            write_ready_contract(paths)
            finalize_campaign_contract(paths, "C-001")
            link_campaign(paths, "RP-001", "C-001")
            activate_campaign(paths, "C-001")
            self.assertEqual(inspect_research_loop(paths).action, "run_planner")

            build_executor_context(paths, "C-001")
            decision = inspect_research_loop(paths)
            self.assertEqual(decision.action, "start_executor")
            self.assertEqual(decision.campaign_id, "C-001")

            claim_executor(paths, "C-001", session_id="goal-session")
            self.assertEqual(inspect_research_loop(paths).action, "monitor_executor")

            artifact = paths.root / "artifacts" / "evidence.txt"
            atomic_write_text(artifact, "evidence\n")
            complete_campaign(paths, "C-001", valid_handoff())
            self.assertEqual(inspect_research_loop(paths).action, "resume_planner")

            persisted = write_loop_state(paths)
            self.assertEqual(persisted["action"], "resume_planner")
            self.assertTrue((paths.runtime / "next-research-action.md").exists())

    def test_ready_campaign_with_tampered_pack_cannot_start(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_research_plan(paths, user_intent="Win")
            create_campaign(paths, title="Signal", goal="Test signal")
            write_ready_contract(paths)
            finalize_campaign_contract(paths, "C-001")
            link_campaign(paths, "RP-001", "C-001")
            activate_campaign(paths, "C-001")
            pack = build_executor_context(paths, "C-001")
            pack.output.write_text(pack.output.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            decision = inspect_research_loop(paths)
            self.assertEqual(decision.action, "run_planner")
            self.assertIn("invalid", decision.reason)


if __name__ == "__main__":
    unittest.main()
