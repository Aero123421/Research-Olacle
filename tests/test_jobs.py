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
from codex_research_harness.utils import atomic_write_json, atomic_write_text, read_json
from tests.helpers import make_repo, ready_contract


class JobLedgerTests(unittest.TestCase):
    def _active_campaign(self, paths, campaign_id: str = "C-001") -> str:
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
        claimed = claim_executor(paths, campaign_id, session_id=f"goal-{campaign_id}")
        return str(claimed["executor"]["claim_id"])

    def test_job_registration_requires_ready_campaign_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(
                paths,
                title="test",
                goal="goal",
                campaign_id="C-001",
                contract=ready_contract(),
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "cannot authorize Jobs"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Too early",
                    resource="GPU0",
                    planned_hours=1,
                )

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
                start_job(paths, "JOB-UNCLAIMED", claim_id="not-a-claim")

    def test_gpu_job_lifecycle_and_campaign_sync(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            job = register_job(
                paths,
                campaign_id="C-001",
                name="Full CV",
                resource="GPU0",
                planned_hours=4,
                job_id="JOB-C001-CV",
                claim_id=claim_id,
            )
            self.assertEqual(job["status"], "queued")
            self.assertEqual(job["resource_kind"], "gpu")
            self.assertEqual(gpu_queue(paths)[0]["job_id"], "JOB-C001-CV")
            start_job(paths, "JOB-C001-CV", claim_id=claim_id)
            heartbeat_job(
                paths,
                "JOB-C001-CV",
                claim_id=claim_id,
                progress="fold 2/5",
                actual_wall_hours=1.5,
                actual_gpu_hours=1.4,
            )
            finished = finish_job(
                paths,
                "JOB-C001-CV",
                claim_id=claim_id,
                actual_wall_hours=3.0,
                actual_gpu_hours=2.8,
            )
            self.assertEqual(finished["executor_claim_id"], claim_id)
            state = sync_campaign_resources(paths, "C-001")
            self.assertEqual(state["resources"]["wall_hours_used"], 3.0)
            self.assertEqual(state["resources"]["gpu_hours_used"], 2.8)
            self.assertEqual(gpu_queue(paths), [])

    def test_runtime_overage_requests_cancellation_without_claiming_process_stop(self) -> None:
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
            claimed = claim_executor(paths, "C-001", session_id="goal-C-001")
            claim_id = claimed["executor"]["claim_id"]
            register_job(
                paths,
                campaign_id="C-001",
                name="long run",
                resource="GPU0",
                planned_hours=10,
                job_id="JOB-OVERAGE",
                claim_id=claim_id,
            )
            start_job(paths, "JOB-OVERAGE", claim_id=claim_id)
            with self.assertRaisesRegex(ResourceAuthorizationError, "daily GPU"):
                heartbeat_job(
                    paths,
                    "JOB-OVERAGE",
                    claim_id=claim_id,
                    actual_wall_hours=21.0,
                    actual_gpu_hours=21.0,
                )
            requested = [job for job in gpu_queue(paths) if job["job_id"] == "JOB-OVERAGE"][0]
            self.assertTrue(requested["stop_required"])
            self.assertEqual(requested["cancellation"]["state"], "requested")
            self.assertTrue(requested["progress"].startswith("CANCELLATION REQUESTED:"))
            self.assertNotIn("HARD STOP", requested["progress"])

            with self.assertRaisesRegex(ValueError, "external stop confirmation"):
                finish_job(
                    paths,
                    "JOB-OVERAGE",
                    claim_id=claim_id,
                    status="cancelled",
                    failure_summary="Budget monitor requested cancellation",
                    actual_wall_hours=21.0,
                    actual_gpu_hours=21.0,
                )

            cancelled = finish_job(
                paths,
                "JOB-OVERAGE",
                claim_id=claim_id,
                status="cancelled",
                failure_summary="Budget monitor requested cancellation",
                actual_wall_hours=21.0,
                actual_gpu_hours=21.0,
                external_stop_confirmed=True,
                external_stop_reference="local-process:JOB-OVERAGE:stopped",
            )
            self.assertEqual(cancelled["cancellation"]["state"], "confirmed")
            self.assertEqual(
                cancelled["cancellation"]["confirmation_basis"],
                "external_stop_reference",
            )
            self.assertTrue(cancelled["cancellation"]["external_stop_confirmed"])
            self.assertFalse(cancelled["stop_required"])

    def test_queue_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            register_job(
                paths,
                campaign_id="C-001",
                name="A",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-A",
                claim_id=claim_id,
            )
            register_job(
                paths,
                campaign_id="C-001",
                name="B",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-B",
                queue_after="JOB-A",
                claim_id=claim_id,
            )
            with self.assertRaises(ValueError):
                start_job(paths, "JOB-B", claim_id=claim_id)
            start_job(paths, "JOB-A", claim_id=claim_id)
            with patch("codex_research_harness.jobs._elapsed_hours", return_value=1.0):
                finish_job(paths, "JOB-A", claim_id=claim_id)
            self.assertEqual(start_job(paths, "JOB-B", claim_id=claim_id)["status"], "running")

    def test_gpu_exclusivity_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            register_job(
                paths,
                campaign_id="C-001",
                name="A",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-A",
                claim_id=claim_id,
            )
            register_job(
                paths,
                campaign_id="C-001",
                name="B",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-B",
                claim_id=claim_id,
            )
            start_job(paths, "JOB-A", claim_id=claim_id)
            with self.assertRaisesRegex(ResourceAuthorizationError, "already in use"):
                start_job(paths, "JOB-B", claim_id=claim_id)

    def test_typed_resource_capacity_applies_to_cpu_as_well_as_gpu(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            for job_id in ("JOB-CPU-A", "JOB-CPU-B"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name=job_id,
                    resource="CPU",
                    planned_hours=1,
                    job_id=job_id,
                    claim_id=claim_id,
                )
            start_job(paths, "JOB-CPU-A", claim_id=claim_id)
            with self.assertRaisesRegex(ResourceAuthorizationError, "already in use"):
                start_job(paths, "JOB-CPU-B", claim_id=claim_id)

    def test_remote_gpu_capacity_is_not_blocked_by_local_parallel_limit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            atomic_write_text(
                paths.local / "compute.toml",
                "[backends.kaggle_notebook]\nenabled = true\n[resources.Kaggle]\nenabled = true\n",
            )
            register_job(
                paths,
                campaign_id="C-001",
                name="Local",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-LOCAL",
                claim_id=claim_id,
            )
            register_job(
                paths,
                campaign_id="C-001",
                name="Remote",
                resource="Kaggle",
                backend="kaggle_notebook",
                planned_hours=1,
                job_id="JOB-REMOTE",
                claim_id=claim_id,
            )
            start_job(paths, "JOB-LOCAL", claim_id=claim_id)
            self.assertEqual(
                start_job(paths, "JOB-REMOTE", claim_id=claim_id)["status"],
                "running",
            )

    def test_reported_usage_cannot_decrease(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            register_job(
                paths,
                campaign_id="C-001",
                name="Measured",
                resource="GPU0",
                planned_hours=2,
                job_id="JOB-MEASURED",
                claim_id=claim_id,
            )
            start_job(paths, "JOB-MEASURED", claim_id=claim_id)
            heartbeat_job(
                paths,
                "JOB-MEASURED",
                claim_id=claim_id,
                actual_wall_hours=1.0,
                actual_gpu_hours=0.9,
            )
            with self.assertRaisesRegex(ValueError, "cannot decrease"):
                heartbeat_job(
                    paths,
                    "JOB-MEASURED",
                    claim_id=claim_id,
                    actual_wall_hours=0.5,
                    actual_gpu_hours=0.4,
                )

    def test_campaign_budget_is_enforced_before_registration(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            register_job(
                paths,
                campaign_id="C-001",
                name="Large run",
                resource="GPU0",
                planned_hours=7.5,
                job_id="JOB-A",
                claim_id=claim_id,
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "exceeds"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Over budget",
                    resource="GPU0",
                    planned_hours=1.0,
                    job_id="JOB-B",
                    claim_id=claim_id,
                )

    def test_queued_gpu_reservations_count_against_the_current_day(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            atomic_write_text(
                paths.local / "compute.toml",
                "[local]\nmax_gpu_hours_per_day = 4.5\n",
            )
            register_job(
                paths,
                campaign_id="C-001",
                name="Queued yesterday",
                resource="GPU0",
                planned_hours=4,
                job_id="JOB-OLD-QUEUE",
                claim_id=claim_id,
            )
            store_path = paths.runtime / "jobs.json"
            store = read_json(store_path)
            store["jobs"][0]["created_at"] = "2000-01-01T00:00:00+00:00"
            atomic_write_json(store_path, store)

            with self.assertRaisesRegex(ResourceAuthorizationError, "local GPU use today"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Today's reservation",
                    resource="GPU1",
                    planned_hours=1,
                    job_id="JOB-TODAY",
                    claim_id=claim_id,
                )

    def test_finalization_gate_rejects_new_exploration(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            update_campaign_state(
                paths,
                "C-001",
                {"resources": {"wall_hours_used": 7.0, "gpu_hours_used": 6.5, "cost_jpy": 0}},
                claim_id=claim_id,
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "finalization-only"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="new branch",
                    resource="GPU0",
                    planned_hours=0.25,
                    job_id="JOB-EXPLORE",
                    claim_id=claim_id,
                )
            final = register_job(
                paths,
                campaign_id="C-001",
                name="confirmation",
                resource="GPU0",
                planned_hours=0.25,
                finalization=True,
                job_id="JOB-CONFIRM",
                claim_id=claim_id,
            )
            self.assertTrue(final["finalization"])

    def test_unknown_or_mismatched_resources_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            with self.assertRaisesRegex(ResourceAuthorizationError, "not registered"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Bypass accounting",
                    resource="RTX5090",
                    planned_hours=1,
                    claim_id=claim_id,
                )
            atomic_write_text(
                paths.local / "compute.toml",
                "[backends.kaggle_notebook]\nenabled = true\n",
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "belongs to backend"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Wrong backend",
                    resource="GPU0",
                    backend="kaggle_notebook",
                    planned_hours=1,
                    claim_id=claim_id,
                )

    def test_superseded_claim_cannot_mutate_bound_job(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            first_claim = self._active_campaign(paths)
            register_job(
                paths,
                campaign_id="C-001",
                name="Long job",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-FENCED",
                claim_id=first_claim,
            )
            start_job(paths, "JOB-FENCED", claim_id=first_claim)

            state_path = paths.campaigns / "C-001" / "STATE.json"
            state = read_json(state_path)
            state["executor"]["lease_expires_at"] = "2000-01-01T00:00:00+00:00"
            atomic_write_json(state_path, state)
            build_executor_context(paths, "C-001")
            with self.assertRaisesRegex(ValueError, "outstanding Jobs"):
                claim_executor(
                    paths,
                    "C-001",
                    session_id="replacement",
                    allow_stale_takeover=True,
                )
            with self.assertRaisesRegex(ResourceAuthorizationError, "expired"):
                heartbeat_job(paths, "JOB-FENCED", claim_id=first_claim)
            with self.assertRaisesRegex(ValueError, "only fail or cancel"):
                finish_job(
                    paths,
                    "JOB-FENCED",
                    status="completed",
                    force_stale_claim=True,
                    failure_summary="operator recovery",
                )
            with self.assertRaisesRegex(ValueError, "external stop confirmation"):
                finish_job(
                    paths,
                    "JOB-FENCED",
                    status="failed",
                    force_stale_claim=True,
                    failure_summary="Original Executor disappeared during execution",
                )
            with self.assertRaisesRegex(ValueError, "external stop confirmation"):
                finish_job(
                    paths,
                    "JOB-FENCED",
                    status="cancelled",
                    force_stale_claim=True,
                    failure_summary="Original Executor lease expired during execution",
                )
            reconciled = finish_job(
                paths,
                "JOB-FENCED",
                status="cancelled",
                force_stale_claim=True,
                failure_summary="Original Executor lease expired during execution",
                external_stop_confirmed=True,
                external_stop_reference="local-process:JOB-FENCED:stopped",
            )
            self.assertTrue(reconciled["force_reconciled"])
            self.assertEqual(
                reconciled["cancellation"]["confirmation_basis"],
                "external_stop_reference",
            )
            build_executor_context(paths, "C-001")

            replacement = claim_executor(
                paths,
                "C-001",
                session_id="replacement",
                allow_stale_takeover=True,
            )
            self.assertNotEqual(replacement["executor"]["claim_id"], first_claim)
            self.assertEqual(replacement["executor"]["generation"], 2)
            with self.assertRaisesRegex(ValueError, "already cancelled"):
                start_job(
                    paths,
                    "JOB-FENCED",
                    claim_id=replacement["executor"]["claim_id"],
                )

    def test_running_failure_requires_observed_exit_or_confirmed_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            job = register_job(
                paths,
                campaign_id="C-001",
                name="Process failure",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-FAILED-EXIT",
                claim_id=claim_id,
            )
            self.assertIsNone(job["control_adapter"])
            start_job(paths, "JOB-FAILED-EXIT", claim_id=claim_id)
            with self.assertRaisesRegex(ValueError, "observed process exit_code"):
                finish_job(
                    paths,
                    "JOB-FAILED-EXIT",
                    claim_id=claim_id,
                    status="failed",
                    failure_summary="Process disappeared",
                )
            failed = finish_job(
                paths,
                "JOB-FAILED-EXIT",
                claim_id=claim_id,
                status="failed",
                exit_code=137,
                failure_summary="Process exited after resource pressure",
            )
            self.assertEqual(failed["exit_code"], 137)

    def test_force_stale_reconciliation_cannot_bypass_a_live_claim(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            register_job(
                paths,
                campaign_id="C-001",
                name="Live job",
                resource="GPU0",
                planned_hours=1,
                job_id="JOB-LIVE",
                claim_id=claim_id,
            )
            start_job(paths, "JOB-LIVE", claim_id=claim_id)
            with self.assertRaisesRegex(ResourceAuthorizationError, "current live Executor claim"):
                finish_job(
                    paths,
                    "JOB-LIVE",
                    status="cancelled",
                    force_stale_claim=True,
                    failure_summary="Improper recovery attempt",
                    external_stop_confirmed=True,
                    external_stop_reference="operator:test-only",
                )

    def test_paid_compute_fails_closed_without_implemented_control_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            contract = ready_contract()
            contract["budget"]["paid_compute_jpy"] = 5000
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
            claimed = claim_executor(paths, "C-001", session_id="goal-C-001")
            claim_id = claimed["executor"]["claim_id"]
            atomic_write_text(
                paths.local / "compute.toml",
                """[paid_compute]
enabled = true
monthly_hard_limit_jpy = 10000
per_job_hard_limit_jpy = 5000
require_auto_shutdown = true
require_cost_metering = true

[backends.local_windows]
enabled = true
cancellation_mode = "enforced"
cost_metering = true
control_adapter = "not-implemented"
""",
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "no implemented control adapter"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Paid run",
                    resource="GPU0",
                    planned_hours=1,
                    planned_cost_jpy=1000,
                    claim_id=claim_id,
                )

    def test_paid_backend_cannot_hide_behind_a_zero_cost_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            contract = ready_contract()
            contract["budget"]["paid_compute_jpy"] = 5000
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
            claim_id = claim_executor(paths, "C-001", session_id="goal-C-001")["executor"]["claim_id"]
            atomic_write_text(
                paths.local / "compute.toml",
                """[backends.ssh_gpu]
enabled = true

[resources."SSH GPU"]
enabled = true
""",
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "positive planned_cost_jpy"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Hidden paid run",
                    backend="ssh_gpu",
                    resource="SSH GPU",
                    planned_hours=1,
                    planned_cost_jpy=0,
                    claim_id=claim_id,
                )

    def test_custom_backend_must_declare_whether_it_is_paid(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim_id = self._active_campaign(paths)
            atomic_write_text(
                paths.local / "compute.toml",
                """[backends.custom_gpu]
enabled = true
cancellation_mode = "cooperative"
cost_metering = false
control_adapter = "none"

[resources.Custom]
enabled = true
kind = "gpu"
backend = "custom_gpu"
capacity = 1
""",
            )
            with self.assertRaisesRegex(ResourceAuthorizationError, "declare paid"):
                register_job(
                    paths,
                    campaign_id="C-001",
                    name="Untyped backend",
                    backend="custom_gpu",
                    resource="Custom",
                    planned_hours=1,
                    claim_id=claim_id,
                )

    def test_unplanned_paid_usage_requests_stop_without_a_code_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            contract = ready_contract()
            contract["budget"]["paid_compute_jpy"] = 5000
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
            claim_id = claim_executor(paths, "C-001", session_id="goal-C-001")["executor"]["claim_id"]
            atomic_write_text(
                paths.local / "compute.toml",
                """[paid_compute]
enabled = true
monthly_hard_limit_jpy = 10000
per_job_hard_limit_jpy = 5000
require_auto_shutdown = true
require_cost_metering = true

[backends.local_windows]
enabled = true
cancellation_mode = "enforced"
cost_metering = true
control_adapter = "not-implemented"
""",
            )
            register_job(
                paths,
                campaign_id="C-001",
                name="Unexpected billable run",
                resource="GPU0",
                planned_hours=1,
                planned_cost_jpy=0,
                job_id="JOB-UNPLANNED-PAID",
                claim_id=claim_id,
            )
            start_job(paths, "JOB-UNPLANNED-PAID", claim_id=claim_id)
            with self.assertRaisesRegex(ResourceAuthorizationError, "implemented control adapter"):
                heartbeat_job(
                    paths,
                    "JOB-UNPLANNED-PAID",
                    claim_id=claim_id,
                    actual_wall_hours=0.1,
                    actual_gpu_hours=0.1,
                    actual_cost_jpy=100,
                )

    def test_paid_compute_accepts_only_a_code_registered_control_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            contract = ready_contract()
            contract["budget"]["paid_compute_jpy"] = 5000
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
            claimed = claim_executor(paths, "C-001", session_id="goal-C-001")
            claim_id = claimed["executor"]["claim_id"]
            atomic_write_text(
                paths.local / "compute.toml",
                """[paid_compute]
enabled = true
monthly_hard_limit_jpy = 10000
per_job_hard_limit_jpy = 5000
require_auto_shutdown = true
require_cost_metering = true

[backends.local_windows]
enabled = true
cancellation_mode = "enforced"
cost_metering = true
control_adapter = "test-provider"
""",
            )
            capabilities = {
                "test-provider": {
                    "enforced_cancellation": True,
                    "provider_cost_metering": True,
                }
            }
            with patch.dict(
                "codex_research_harness.jobs.IMPLEMENTED_BACKEND_CONTROLS",
                capabilities,
                clear=True,
            ):
                job = register_job(
                    paths,
                    campaign_id="C-001",
                    name="Paid run",
                    resource="GPU0",
                    planned_hours=1,
                    planned_cost_jpy=1000,
                    claim_id=claim_id,
                )
            self.assertEqual(job["planned_cost_jpy"], 1000)
            self.assertEqual(job["control_adapter"], "test-provider")


if __name__ == "__main__":
    unittest.main()
