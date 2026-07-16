from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.campaign import create_campaign
from codex_research_harness.plans import (
    PlanStateConflictError,
    create_research_plan,
    link_campaign,
    list_plan_ids,
    transition_research_plan,
    update_research_plan,
)
from tests.helpers import make_repo


class ResearchPlanTests(unittest.TestCase):
    def test_plan_lifecycle_is_explicit_and_revisioned(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            directory = create_research_plan(
                paths, user_intent="Win the competition", target="example", plan_id="RP-001"
            )
            self.assertTrue((directory / "PLAN.md").exists())

            checkpoint = update_research_plan(
                paths,
                "RP-001",
                {"current_action": "Build the first Evidence Pack"},
                expected_revision=0,
            )
            self.assertEqual(checkpoint["revision"], 1)
            with self.assertRaisesRegex(ValueError, "authoritative field"):
                update_research_plan(paths, "RP-001", {"status": "researching"})

            state = transition_research_plan(
                paths,
                "RP-001",
                status="researching",
                current_action="Survey the landscape",
                expected_revision=checkpoint["revision"],
            )
            self.assertEqual(state["status"], "researching")
            self.assertEqual(state["revision"], 2)

            create_campaign(paths, title="test", goal="goal", campaign_id="C-001")
            with self.assertRaisesRegex(ValueError, "cannot transition"):
                link_campaign(
                    paths,
                    "RP-001",
                    "C-001",
                    expected_revision=state["revision"],
                )

            ready = transition_research_plan(
                paths,
                "RP-001",
                status="ready",
                current_action="Launch the selected bounded Campaign",
                expected_revision=state["revision"],
            )
            linked = link_campaign(
                paths,
                "RP-001",
                "C-001",
                expected_revision=ready["revision"],
            )
            self.assertEqual(linked["selected_campaign"], "C-001")
            self.assertEqual(linked["status"], "campaign_running")

            with self.assertRaises(PlanStateConflictError):
                transition_research_plan(
                    paths,
                    "RP-001",
                    status="replanning",
                    expected_revision=state["revision"],
                )

            replanning = transition_research_plan(
                paths,
                "RP-001",
                status="replanning",
                current_action="Synthesize the Campaign Handoff",
                expected_revision=linked["revision"],
            )
            self.assertEqual(replanning["strategy_epoch"], 2)

    def test_plan_ids_are_sorted_numerically(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            plans = paths.research / "plans"
            for plan_id in ("RP-1000", "RP-999", "RP-010"):
                (plans / plan_id).mkdir(parents=True)
            self.assertEqual(list_plan_ids(paths), ["RP-010", "RP-999", "RP-1000"])


if __name__ == "__main__":
    unittest.main()
