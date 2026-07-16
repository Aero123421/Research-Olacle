from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.campaign import (
    CampaignStateConflictError,
    ExecutorClaimError,
    activate_campaign,
    claim_executor,
    complete_campaign,
    create_campaign,
    finalize_campaign_contract,
    heartbeat_executor,
    list_campaign_ids,
    transition_campaign_state,
    update_campaign_state,
)
from codex_research_harness.context import build_executor_context
from codex_research_harness.schema import ValidationError
from codex_research_harness.utils import atomic_write_json, atomic_write_text, read_json
from tests.helpers import make_repo, valid_handoff, write_ready_contract


class CampaignTests(unittest.TestCase):
    def _claimed_campaign(self, paths) -> tuple[Path, dict]:
        directory = create_campaign(paths, title="Explore", goal="Find evidence")
        write_ready_contract(paths)
        finalize_campaign_contract(paths, "C-001")
        activate_campaign(paths, "C-001")
        build_executor_context(paths, "C-001")
        claimed = claim_executor(paths, "C-001", session_id="goal-C-001")
        return directory, claimed

    def test_draft_cannot_activate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(paths, title="Explore", goal="Find evidence")
            with self.assertRaises(ValidationError):
                activate_campaign(paths, "C-001")

    def test_campaign_lifecycle_and_budget_gates(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            directory, claimed = self._claimed_campaign(paths)
            claim_id = claimed["executor"]["claim_id"]

            state = update_campaign_state(
                paths,
                "C-001",
                {
                    "resources": {"wall_hours_used": 4.0, "gpu_hours_used": 2.0, "cost_jpy": 0},
                },
                claim_id=claim_id,
            )
            state = transition_campaign_state(
                paths,
                "C-001",
                claim_id=claim_id,
                status="validating",
                phase="quick",
                expected_revision=state["revision"],
            )
            self.assertEqual(state["budget_status"], "early_review")

            evidence = paths.root / "artifacts" / "evidence.txt"
            atomic_write_text(evidence, "reproducible evidence\n")
            handoff = valid_handoff()
            handoff["resources_actual"] = {"wall_hours": 4.0, "gpu_hours": 2.0, "cost_jpy": 0}
            completed = complete_campaign(paths, "C-001", handoff, claim_id=claim_id)
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["executor"]["status"], "released")
            self.assertEqual(read_json(directory / "HANDOFF.json")["outcome"], "rejected_with_evidence")
            self.assertIn("No stable improvement", (directory / "HANDOFF.md").read_text(encoding="utf-8"))

    def test_executor_claim_is_atomic_exclusive_and_fenced(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            _, claimed = self._claimed_campaign(paths)
            first_claim = claimed["executor"]["claim_id"]
            self.assertEqual(claimed["executor"]["generation"], 1)

            with self.assertRaisesRegex(ValueError, "already claimed"):
                claim_executor(paths, "C-001", session_id="session-two")

            renewed = heartbeat_executor(
                paths,
                "C-001",
                claim_id=first_claim,
                session_id="session-one",
                lease_minutes=60,
            )
            self.assertEqual(renewed["executor"]["claim_id"], first_claim)

            state_path = paths.campaigns / "C-001" / "STATE.json"
            stale = read_json(state_path)
            stale["executor"]["lease_expires_at"] = "2000-01-01T00:00:00+00:00"
            atomic_write_json(state_path, stale)
            build_executor_context(paths, "C-001")
            replacement = claim_executor(
                paths,
                "C-001",
                session_id="session-two",
                allow_stale_takeover=True,
            )
            self.assertEqual(replacement["executor"]["generation"], 2)
            self.assertEqual(replacement["executor_history"][-1]["claim_id"], first_claim)
            self.assertEqual(replacement["executor_history"][-1]["status"], "superseded")
            with self.assertRaises(ExecutorClaimError):
                heartbeat_executor(paths, "C-001", claim_id=first_claim)

    def test_checkpoint_rejects_authoritative_fields_and_stale_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            _, claimed = self._claimed_campaign(paths)
            claim_id = claimed["executor"]["claim_id"]
            with self.assertRaisesRegex(ValueError, "authoritative field"):
                update_campaign_state(
                    paths,
                    "C-001",
                    {"status": "completed", "executor": {}},
                    claim_id=claim_id,
                )

            with self.assertRaisesRegex(ValueError, "authoritative field"):
                update_campaign_state(
                    paths,
                    "C-001",
                    {"phase": "quick"},
                    claim_id=claim_id,
                )

            revision = claimed["revision"]
            updated = update_campaign_state(
                paths,
                "C-001",
                {"current_action": "Run quick validation"},
                claim_id=claim_id,
                expected_revision=revision,
            )
            self.assertEqual(updated["revision"], revision + 1)
            with self.assertRaises(CampaignStateConflictError):
                update_campaign_state(
                    paths,
                    "C-001",
                    {"current_action": "Run full CV"},
                    claim_id=claim_id,
                    expected_revision=revision,
                )

    def test_active_lifecycle_changes_use_explicit_claimed_transition(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            _, claimed = self._claimed_campaign(paths)
            claim_id = claimed["executor"]["claim_id"]
            transitioned = transition_campaign_state(
                paths,
                "C-001",
                claim_id=claim_id,
                status="validating",
                phase="confirmation",
                current_action="Confirm the strongest result",
                expected_revision=claimed["revision"],
            )
            self.assertEqual(transitioned["status"], "validating")
            self.assertEqual(transitioned["phase"], "confirmation")
            renewed = heartbeat_executor(paths, "C-001", claim_id=claim_id)
            self.assertEqual(renewed["status"], "validating")

    def test_resource_accounting_is_monotonic(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            _, claimed = self._claimed_campaign(paths)
            claim_id = claimed["executor"]["claim_id"]
            updated = update_campaign_state(
                paths,
                "C-001",
                {"resources": {"wall_hours_used": 2.0, "gpu_hours_used": 1.0, "cost_jpy": 10}},
                claim_id=claim_id,
            )
            with self.assertRaisesRegex(ValueError, "cannot decrease"):
                update_campaign_state(
                    paths,
                    "C-001",
                    {"resources": {"wall_hours_used": 1.0}},
                    claim_id=claim_id,
                    expected_revision=updated["revision"],
                )

    def test_campaign_ids_are_sorted_numerically(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            for campaign_id in ("C-1000", "C-999", "C-010"):
                (paths.campaigns / campaign_id).mkdir()
            self.assertEqual(list_campaign_ids(paths), ["C-010", "C-999", "C-1000"])

    def test_completion_rejects_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            _, claimed = self._claimed_campaign(paths)
            with self.assertRaises(FileNotFoundError):
                complete_campaign(
                    paths,
                    "C-001",
                    valid_handoff(artifact="artifacts/missing.txt"),
                    claim_id=claimed["executor"]["claim_id"],
                )

    def test_completion_rejects_outstanding_jobs(self) -> None:
        from codex_research_harness.jobs import register_job

        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            _, claimed = self._claimed_campaign(paths)
            claim_id = claimed["executor"]["claim_id"]
            register_job(
                paths,
                campaign_id="C-001",
                name="Still queued",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-PENDING",
                claim_id=claim_id,
            )
            atomic_write_text(paths.root / "artifacts" / "evidence.txt", "evidence\n")
            with self.assertRaisesRegex(ValueError, "outstanding jobs"):
                complete_campaign(paths, "C-001", valid_handoff(), claim_id=claim_id)

    def test_completion_rejects_resource_under_reporting(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            _, claimed = self._claimed_campaign(paths)
            claim_id = claimed["executor"]["claim_id"]
            update_campaign_state(
                paths,
                "C-001",
                {"resources": {"wall_hours_used": 3.0, "gpu_hours_used": 2.0, "cost_jpy": 0}},
                claim_id=claim_id,
            )
            atomic_write_text(paths.root / "artifacts" / "evidence.txt", "evidence\n")
            with self.assertRaisesRegex(ValueError, "under-reports"):
                complete_campaign(paths, "C-001", valid_handoff(), claim_id=claim_id)


if __name__ == "__main__":
    unittest.main()
