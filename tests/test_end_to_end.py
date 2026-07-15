from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.bootstrap import initialize_repository
from codex_research_harness.campaign import (
    activate_campaign,
    complete_campaign,
    create_campaign,
    finalize_campaign_contract,
)
from codex_research_harness.consultation import (
    prepare_consultation,
    record_chatgpt_project,
    record_consultation_response,
    record_consultation_synthesis,
    verify_chatgpt_project,
)
from codex_research_harness.context import build_executor_context, build_planner_context
from codex_research_harness.experiments import register_experiment
from codex_research_harness.github import GitHubClient
from codex_research_harness.jobs import finish_job, register_job, start_job, sync_campaign_resources
from codex_research_harness.plans import create_research_plan, link_campaign, update_research_plan
from codex_research_harness.utils import atomic_write_text
from codex_research_harness.visualize import generate_all
from tests.helpers import make_repo, ready_contract, valid_handoff


class EndToEndResearchLoopTests(unittest.TestCase):
    def test_planner_goal_handoff_replan_loop_survives_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))

            # First-run state and browser choice are durable and resumable.
            initialized = initialize_repository(
                paths,
                answers={
                    "browser": {"mode": "built_in", "chrome_profile": None},
                    "compute": {
                        "local_gpu_max_hours_per_day": 20.0,
                        "campaign_gpu_hours_default": 8.0,
                        "paid_compute_enabled": False,
                        "paid_compute_monthly_limit_jpy": 0.0,
                        "paid_compute_per_job_limit_jpy": 0.0,
                    },
                },
            )
            self.assertEqual(initialized["browser_mode"], "built_in")

            # The browser Skill owns UI automation; the CLI owns validated durable state.
            project = record_chatgpt_project(
                paths,
                browser_mode="built_in",
                project_name="CRH • example/research • 12345678",
                project_url="https://chatgpt.com/g/g-p-example/project",
                selected_model_label="Pro",
                model_preference=["Pro"],
                available_model_labels=["Instant", "High", "Pro"],
            )
            self.assertEqual(project["status"], "needs_verification")
            verified = verify_chatgpt_project(
                paths,
                actual_model_label="Pro",
                project_url=project["project_url"],
                project_name=project["project_name"],
            )
            self.assertEqual(verified["status"], "ready")

            plan_dir = create_research_plan(
                paths,
                user_intent="このKaggleコンペでPrivate Leaderboard 1位を狙いたい。",
                target="https://www.kaggle.com/competitions/example",
                deadline="2026-08-31T23:59:00+09:00",
            )
            update_research_plan(
                paths,
                "RP-001",
                {
                    "status": "researching",
                    "current_action": "Inspect rules, EDA, baseline, domain landscape, and independent advisors",
                },
            )

            question_dir = prepare_consultation(
                paths,
                question="Evidence Packを自由に再解釈し、見落とした勝ち筋と最小反証実験を提案してください。",
                purpose="broad strategy synthesis",
                requester_role="research-planner",
                context_files=["research/strategy/EVIDENCE_INDEX.md"],
            )
            self.assertEqual(question_dir.name, "Q-0001")
            response = record_consultation_response(
                paths,
                question_id="Q-0001",
                conversation_url="https://chatgpt.com/c/example-conversation",
                response_text="独立した戦略候補と反証実験を整理した。",
                actual_model_label="Pro",
            )
            self.assertEqual(response["status"], "completed")
            record_consultation_synthesis(
                paths,
                question_id="Q-0001",
                synthesis_text="Candidate strategy is unverified; test it with the fixed evaluation contract.",
            )

            campaign_dir = create_campaign(
                paths,
                title="Test a robust and complementary signal family",
                goal="Determine whether the signal improves fixed validation and ensemble diversity",
                contract=ready_contract(),
            )
            self.assertTrue(campaign_dir.exists())
            finalize_campaign_contract(paths, "C-001")
            link_campaign(paths, "RP-001", "C-001")
            activate_campaign(paths, "C-001")

            executor_pack = build_executor_context(paths, "C-001")
            self.assertIn("research/campaigns/C-001/CONTRACT.json", executor_pack.included)
            self.assertNotIn("research/USER_INTENT.md", executor_pack.included)
            self.assertTrue((campaign_dir / "GOAL_PROMPT.md").exists())

            job = register_job(
                paths,
                campaign_id="C-001",
                name="quick-validation",
                resource="GPU0",
                planned_hours=1.0,
                backend="local_windows",
                command_summary="python experiments/quick.py",
            )
            start_job(paths, job["job_id"])
            finish_job(
                paths,
                job["job_id"],
                actual_wall_hours=0.75,
                actual_gpu_hours=0.70,
            )
            synced = sync_campaign_resources(paths, "C-001")
            self.assertEqual(synced["resources"]["gpu_hours_used"], 0.7)

            artifact = paths.root / "artifacts" / "evidence.txt"
            atomic_write_text(artifact, "fixed-CV evidence\n")
            registered = register_experiment(
                paths,
                {
                    "experiment_id": "EXP-001",
                    "campaign_id": "C-001",
                    "hypothesis": "The proposed signal improves robust validation",
                    "status": "completed",
                    "git_commit": "0123456789abcdef",
                    "metrics": {"cv_delta": -0.0003},
                    "resources": {"wall_hours": 0.75, "gpu_hours": 0.70},
                    "artifacts": ["artifacts/evidence.txt"],
                },
            )
            self.assertTrue(registered["artifacts"][0]["exists"])

            handoff = valid_handoff()
            handoff["resources_actual"] = {"wall_hours": 0.75, "gpu_hours": 0.70, "cost_jpy": 0}
            completed = complete_campaign(paths, "C-001", handoff)
            self.assertEqual(completed["status"], "completed")

            update_research_plan(
                paths,
                "RP-001",
                {
                    "status": "replanning",
                    "current_action": "Synthesize C-001 evidence and select the next bounded Campaign",
                },
            )
            planner_pack = build_planner_context(paths)
            planner_text = planner_pack.output.read_text(encoding="utf-8")
            self.assertIn("Planner handoff — C-001", planner_text)
            self.assertIn("Bounded consultation synthesis — Q-0001", planner_text)
            self.assertNotIn("独立した戦略候補と反証実験を整理した", planner_text)
            self.assertNotIn("conversation URL", planner_text)
            self.assertTrue(plan_dir.exists())

            # The human control plane is fully renderable without live GitHub access.
            project_state = GitHubClient(paths, dry_run=True).setup_project()
            campaign_state = GitHubClient(paths, dry_run=True).sync_campaign("C-001")
            self.assertEqual(project_state["views_status"], "requires_browser_configuration")
            self.assertEqual(campaign_state["campaign_id"], "C-001")
            for output in generate_all(paths):
                self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
