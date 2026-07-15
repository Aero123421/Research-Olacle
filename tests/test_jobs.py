from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_research_harness.campaign import (
    activate_campaign,
    claim_executor,
    create_campaign,
    finalize_campaign_contract,
    update_campaign_state,
)
from codex_research_harness.context import build_executor_context
from codex_research_harness.jobs import (
    ResourceAuthorizationError,
    finish_job,
    gpu_queue,
    heartbeat_job,
    register_job,
    start_job,
    sync_campaign_resources,
)
from tests.helpers import make_repo, ready_contract


class JobLedgerTests(unittest.TestCase):
    def _active_campaign(self, paths, campaign_id: str = "C-001") -> None:
        create_campaign(
            paths,
            title="test",
            goal="goal",
            campaign_id=campaign_id,
            contract=ready_contract(campaign_id),
        )
        finalize_campaign_contract(paths, campaign_id)
        activate_campaign(paths, campaign_id)
        build_executor_context(paths, campaign_id)
        claim_executor(paths, campaign_id, session_id=f"goal-{campaign_id}")

    def test_job_start_requires_an_active_executor_claim(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(
                paths,
                title="test",
                goal="goal",
                campaign_id="C-001",
                contract=ready_contract(),
            )
            finalize_campaign_contract(paths, "C-001")
            activate_campaign(paths, "C-001")
            register_job(
                paths,
                campaign_id="C-001",
                name="Full CV",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-UNCLAIMED",
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "no active Executor claim"):
                start_job(paths, "JOB-UNCLAIMED")

    def test_gpu_job_lifecycle_and_campaign_sync(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            self._active_campaign(paths)
            job = register_job(
                paths,
                campaign_id="C-001",
                name="Full CV",
                resource="GPU0",
                planned_hours=4,
                job_id="JOB-C001-CV",
            )
            self.assertEqual(job["status"], "queued")
            self.assertEqual(gpu_queue(paths)[0]["job_id"], "JOB-C001-CV")
            start_job(paths, "JOB-C001-CV")
            heartbeat_job(
                paths,
                "JOB-C001-CV",
                progress="fold 2/5",
                actual_wall_hours=1.5,
                actual_gpu_hours=1.4,
            )
            finish_job(paths, "JOB-C001-CV", actual_wall_hours=3.0, actual_gpu_hours=2.8)
            state = sync_campaign_resources(paths, "C-001")
            self.assertEqual(state["resources"]["wall_hours_used"], 3.0)
            self.assertEqual(state["resources"]["gpu_hours_used"], 2.8)
            self.assertEqual(gpu_queue(paths), [])

    def test_runtime_overage_sets_hard_stop(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            contract = ready_contract()
            contract["budget"] = {"wall_hours": 30.0, "gpu_hours": 30.0, "paid_compute_jpy": 0.0}
            create_campaign(
                paths,
                title="test",
                goal="goal",
                campaign_id="C-001",
                contract=contract,
            )
            finalize_campaign_contract(paths, "C-001")
            activate_campaign(paths, "C-001")
            build_executor_context(paths, "C-001")
            claim_executor(paths, "C-001", session_id="goal-C-001")
            register_job(
                paths,
                campaign_id="C-001",
                name="long run",
                resource="GPU0",
                planned_hours=10,
                job_id="JOB-OVERAGE",
            )
            start_job(paths, "JOB-OVERAGE")
            with self.assertRaisesRegex(ResourceAuthorizationError, "daily GPU"):
                heartbeat_job(
                    paths,
                    "JOB-OVERAGE",
                    actual_wall_hours=21.0,
                    actual_gpu_hours=21.0,
                )
            stopped = [job for job in gpu_queue(paths) if job["job_id"] == "JOB-OVERAGE"][0]
            self.assertTrue(stopped["stop_required"])

    def test_queue_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            self._active_campaign(paths)
            register_job(
                paths, campaign_id="C-001", name="A", resource="GPU0", planned_hours=1, job_id="JOB-A"
            )
            register_job(
                paths,
                campaign_id="C-001",
                name="B",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-B",
                queue_after="JOB-A",
            )
            with self.assertRaises(ValueError):
                start_job(paths, "JOB-B")
            start_job(paths, "JOB-A")
            with patch("codex_research_harness.jobs._elapsed_hours", return_value=1.0):
                finish_job(paths, "JOB-A")
            self.assertEqual(start_job(paths, "JOB-B")["status"], "running")

    def test_gpu_exclusivity_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            self._active_campaign(paths)
            register_job(
                paths, campaign_id="C-001", name="A", resource="GPU0", planned_hours=1, job_id="JOB-A"
            )
            register_job(
                paths, campaign_id="C-001", name="B", resource="GPU0", planned_hours=1, job_id="JOB-B"
            )
            start_job(paths, "JOB-A")
            with self.assertRaisesRegex(ResourceAuthorizationError, "already in use"):
                start_job(paths, "JOB-B")

    def test_campaign_budget_is_enforced_before_registration(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            self._active_campaign(paths)
            register_job(
                paths,
                campaign_id="C-001",
                name="Large run",
                resource="GPU0",
                planned_hours=7.5,
                job_id="JOB-A",
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "exceeds"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Over budget",
                    resource="GPU0",
                    planned_hours=1.0,
                    job_id="JOB-B",
                )

    def test_finalization_gate_rejects_new_exploration(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            self._active_campaign(paths)
            update_campaign_state(
                paths,
                "C-001",
                {"resources": {"wall_hours_used": 7.0, "gpu_hours_used": 6.5, "cost_jpy": 0}},
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "finalization-only"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="new branch",
                    resource="GPU0",
                    planned_hours=0.25,
                    job_id="JOB-EXPLORE",
                )
            final = register_job(
                paths,
                campaign_id="C-001",
                name="confirmation",
                resource="GPU0",
                planned_hours=0.25,
                finalization=True,
                job_id="JOB-CONFIRM",
            )
            self.assertTrue(final["finalization"])


if __name__ == "__main__":
    unittest.main()
