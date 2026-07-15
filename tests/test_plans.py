from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_research_harness.campaign import create_campaign
from codex_research_harness.plans import create_research_plan, link_campaign, update_research_plan
from tests.helpers import make_repo


class ResearchPlanTests(unittest.TestCase):
    def test_plan_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            directory = create_research_plan(
                paths, user_intent="Win the competition", target="example", plan_id="RP-001"
            )
            self.assertTrue((directory / "PLAN.md").exists())
            state = update_research_plan(paths, "RP-001", {"status": "researching"})
            self.assertEqual(state["status"], "researching")
            create_campaign(paths, title="test", goal="goal", campaign_id="C-001")
            linked = link_campaign(paths, "RP-001", "C-001")
            self.assertEqual(linked["selected_campaign"], "C-001")


if __name__ == "__main__":
    unittest.main()
