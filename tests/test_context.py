from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.campaign import activate_campaign, create_campaign, finalize_campaign_contract
from codex_research_harness.context import ContextPackError, build_executor_context, build_planner_context
from tests.helpers import make_repo, write_ready_contract


class ContextTests(unittest.TestCase):
    def test_role_specific_packs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            planner = build_planner_context(paths)
            self.assertTrue(planner.output.exists())
            self.assertIn("Research Planner context", planner.output.read_text(encoding="utf-8"))
            create_campaign(paths, title="Test", goal="Find evidence")
            write_ready_contract(paths)
            finalize_campaign_contract(paths, "C-001")
            activate_campaign(paths, "C-001")
            executor = build_executor_context(paths, "C-001")
            text = executor.output.read_text(encoding="utf-8")
            self.assertIn("Executor context", text)
            self.assertIn("Campaign contract", text)
            self.assertIn("Current campaign state", text)
            self.assertNotIn("Original human intent", text)

    def test_missing_required_evidence_blocks_executor_pack(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            create_campaign(paths, title="Test", goal="Find evidence")
            contract = write_ready_contract(paths)
            contract["evidence_inputs"] = ["research/missing-evidence.md"]
            from codex_research_harness.utils import atomic_write_json

            atomic_write_json(paths.campaigns / "C-001" / "CONTRACT.json", contract)
            finalize_campaign_contract(paths, "C-001")
            with self.assertRaises(ContextPackError):
                build_executor_context(paths, "C-001")


if __name__ == "__main__":
    unittest.main()
