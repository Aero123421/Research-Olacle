from __future__ import annotations

import unittest
from unittest.mock import patch

from codex_research_harness.campaign import create_campaign
from codex_research_harness.jobs import (
    finish_job,
    gpu_queue,
    heartbeat_job,
    register_job,
    start_job,
    sync_campaign_resources,
)
from tests.helpers import make_repo


class JobLedgerTests(unittest.TestCase):
    def test_gpu_job_lifecycle_and_campaign_sync(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(paths, title="test", goal="goal", campaign_id="C-001")
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
                paths, "JOB-C001-CV", progress="fold 2/5", actual_wall_hours=1.5, actual_gpu_hours=1.4
            )
            finish_job(paths, "JOB-C001-CV", actual_wall_hours=3.0, actual_gpu_hours=2.8)
            state = sync_campaign_resources(paths, "C-001")
            self.assertEqual(state["resources"]["wall_hours_used"], 3.0)
            self.assertEqual(state["resources"]["gpu_hours_used"], 2.8)
            self.assertEqual(gpu_queue(paths), [])

    def test_queue_dependency(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(paths, title="test", goal="goal", campaign_id="C-001")
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


if __name__ == "__main__":
    unittest.main()
