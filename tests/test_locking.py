from __future__ import annotations

import json
import os
import socket
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from codex_research_harness.campaign import create_campaign, list_campaign_ids
from codex_research_harness.consultation import (
    prepare_consultation,
    record_chatgpt_project,
    verify_chatgpt_project,
)
from codex_research_harness.locking import LockTimeoutError, file_lock
from codex_research_harness.plans import create_research_plan, list_plan_ids
from tests.helpers import make_repo


class SharedStateLockingTests(unittest.TestCase):
    def test_parallel_campaign_and_plan_id_allocation_is_unique(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))

            def make_campaign(index: int) -> str:
                return create_campaign(
                    paths,
                    title=f"Campaign {index}",
                    goal=f"Test bounded hypothesis {index}",
                ).name

            def make_plan(index: int) -> str:
                return create_research_plan(
                    paths,
                    user_intent=f"Research mission {index}",
                    target="https://example.test",
                ).name

            with ThreadPoolExecutor(max_workers=8) as executor:
                campaigns = list(executor.map(make_campaign, range(12)))
                plans = list(executor.map(make_plan, range(12)))

            self.assertEqual(len(set(campaigns)), 12)
            self.assertEqual(sorted(campaigns), [f"C-{index:03d}" for index in range(1, 13)])
            self.assertEqual(list_campaign_ids(paths), sorted(campaigns))
            self.assertEqual(len(set(plans)), 12)
            self.assertEqual(sorted(plans), [f"RP-{index:03d}" for index in range(1, 13)])
            self.assertEqual(list_plan_ids(paths), sorted(plans))

    def test_old_lock_owned_by_live_process_is_not_stolen(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            lock_path = Path(raw) / "live.lock"
            lock_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "token": "live-owner",
                        "pid": os.getpid(),
                        "host": socket.gethostname(),
                    }
                ),
                encoding="utf-8",
            )
            old = time.time() - 3600
            os.utime(lock_path, (old, old))
            with self.assertRaises(LockTimeoutError):
                with file_lock(
                    lock_path,
                    timeout_seconds=0.05,
                    stale_after_seconds=1,
                    poll_seconds=0.01,
                ):
                    self.fail("A live owner's lock must not be stolen")
            self.assertTrue(lock_path.exists())

    def test_old_lock_with_dead_owner_is_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            lock_path = Path(raw) / "dead.lock"
            lock_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "token": "dead-owner",
                        "pid": 2_147_483_647,
                        "host": socket.gethostname(),
                    }
                ),
                encoding="utf-8",
            )
            old = time.time() - 3600
            os.utime(lock_path, (old, old))
            with file_lock(
                lock_path,
                timeout_seconds=0.2,
                stale_after_seconds=1,
                poll_seconds=0.01,
            ):
                self.assertTrue(lock_path.exists())
            self.assertFalse(lock_path.exists())

    def test_parallel_consultation_id_allocation_is_unique(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            project = record_chatgpt_project(
                paths,
                browser_mode="built_in",
                project_name="CRH • lock-test",
                project_url="https://chatgpt.com/g/g-p-lock-test/project",
                selected_model_label="Pro",
                model_preference=["Pro"],
                available_model_labels=["Pro"],
            )
            verify_chatgpt_project(
                paths,
                actual_model_label="Pro",
                project_url=project["project_url"],
                project_name=project["project_name"],
            )

            def prepare(index: int) -> str:
                return prepare_consultation(
                    paths,
                    question=f"Question {index}",
                    purpose="parallel allocation test",
                    requester_role="research-planner",
                ).name

            with ThreadPoolExecutor(max_workers=8) as executor:
                values = list(executor.map(prepare, range(12)))

            self.assertEqual(len(set(values)), 12)
            self.assertEqual(sorted(values), [f"Q-{index:04d}" for index in range(1, 13)])


if __name__ == "__main__":
    unittest.main()
