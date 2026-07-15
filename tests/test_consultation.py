from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.consultation import (
    choose_preferred_model,
    configure_browser,
    get_consultation_route,
    prepare_consultation,
    record_chatgpt_project,
    record_consultation_response,
    record_consultation_synthesis,
    suggest_chatgpt_project_name,
    verify_chatgpt_project,
)
from tests.helpers import make_repo


class ConsultationTests(unittest.TestCase):
    def test_project_and_new_question_then_follow_up_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            configure_browser(paths, mode="chrome", chrome_profile="Research")
            record_chatgpt_project(
                paths,
                browser_mode="chrome",
                project_name="CRH test",
                project_url="https://chatgpt.com/g/g-p-test/project",
                selected_model_label="Pro",
                available_model_labels=["Instant", "High", "Pro"],
            )
            verify_chatgpt_project(paths, actual_model_label="Pro", project_name="CRH test")
            directory = prepare_consultation(
                paths,
                question="What evidence should distinguish these explanations?",
                purpose="strategy",
                requester_role="research-planner",
            )
            self.assertEqual(directory.name, "Q-0001")
            metadata = record_consultation_response(
                paths,
                question_id="Q-0001",
                conversation_url="https://chatgpt.com/c/example",
                response_text="Run the cheapest discriminating test.",
                actual_model_label="Pro",
            )
            self.assertEqual(metadata["status"], "completed")
            synthesized = record_consultation_synthesis(
                paths,
                question_id="Q-0001",
                synthesis_text="Advisor claim: run the cheapest test. Evidence status: unverified until experiment.",
            )
            self.assertTrue(synthesized["synthesis_available"])
            self.assertTrue((directory / "SYNTHESIS.md").exists())
            self.assertNotIn(
                "chatgpt.com", (paths.setup / "CHATGPT_RESEARCH_PARTNER.md").read_text(encoding="utf-8")
            )
            self.assertEqual(
                get_consultation_route(paths, "Q-0001")["conversation_url"], "https://chatgpt.com/c/example"
            )

            follow_up = prepare_consultation(
                paths,
                question="How should the confirmation test be powered?",
                purpose="same-question clarification",
                requester_role="research-executor",
                follow_up_to="Q-0001",
            )
            self.assertEqual(follow_up.name, "Q-0002")
            self.assertIn("Q-0001", (follow_up / "REQUEST.md").read_text(encoding="utf-8"))

    def test_exact_pro_is_required_without_fuzzy_fallback(self) -> None:
        self.assertEqual(choose_preferred_model(["Instant", "High", "Pro"]), "Pro")
        with self.assertRaises(ValueError):
            choose_preferred_model(["Pro Extended", "High"])

    def test_model_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            record_chatgpt_project(
                paths,
                browser_mode="built_in",
                project_name="CRH test",
                project_url="https://chatgpt.com/project/example",
                selected_model_label="Pro",
            )
            with self.assertRaises(ValueError):
                verify_chatgpt_project(paths, actual_model_label="High")

    def test_stable_project_name_contains_repository_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            value = suggest_chatgpt_project_name(paths)
            self.assertTrue(value.startswith("CRH •"))
            self.assertRegex(value, r"[0-9a-f]{8}$")


if __name__ == "__main__":
    unittest.main()
