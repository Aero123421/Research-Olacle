from __future__ import annotations

import unittest

from codex_research_harness.campaign import default_contract
from codex_research_harness.schema import validate_campaign_contract, validate_campaign_handoff
from tests.helpers import ready_contract, valid_handoff


class SchemaTests(unittest.TestCase):
    def test_default_contract_is_valid_draft_but_not_runnable(self) -> None:
        value = default_contract("C-001", "Test", "Test a useful hypothesis")
        self.assertEqual(validate_campaign_contract(value, require_ready=False), [])
        self.assertTrue(validate_campaign_contract(value, require_ready=True))

    def test_ready_contract_is_runnable(self) -> None:
        self.assertEqual(validate_campaign_contract(ready_contract()), [])

    def test_ready_contract_rejects_unresolved_placeholders(self) -> None:
        value = default_contract("C-001", "Test", "Test")
        value["contract_status"] = "ready"
        self.assertTrue(any("unresolved" in issue.message for issue in validate_campaign_contract(value)))

    def test_invalid_budget_is_rejected(self) -> None:
        value = ready_contract()
        value["budget"]["gpu_hours"] = -1
        self.assertTrue(validate_campaign_contract(value))

    def test_handoff_requires_known_outcome(self) -> None:
        value = valid_handoff()
        value["outcome"] = "magic"
        self.assertTrue(validate_campaign_handoff(value))

    def test_handoff_requires_linked_evidence(self) -> None:
        value = valid_handoff()
        value["evidence"] = [{"artifact": "x"}]
        self.assertTrue(validate_campaign_handoff(value))


if __name__ == "__main__":
    unittest.main()
