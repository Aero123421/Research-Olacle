from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from codex_research_harness.epistemics import (
    EpistemicLedgerError,
    current_claims,
    load_claim_events,
    record_claim,
    update_claim,
)
from tests.helpers import make_repo


class EpistemicLedgerTests(unittest.TestCase):
    def test_claim_events_are_append_only_and_project_current_belief(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            asserted = record_claim(
                paths,
                statement="The signal transfers beyond quick validation",
                confidence=0.4,
                falsifier="Locked confirmation fails to reproduce the gain",
                assumptions=["The evaluation split remains representative"],
                source_campaign="C-001",
            )
            self.assertEqual(asserted["claim_id"], "CLM-0001")
            self.assertEqual(asserted["effective_status"], "tentative")

            corroborated = update_claim(
                paths,
                "CLM-0001",
                status="corroborated",
                confidence=0.8,
                evidence_refs=["artifacts/confirmation.json"],
            )
            self.assertEqual(corroborated["status"], "corroborated")
            events = load_claim_events(paths)
            self.assertEqual(len(events), 2)
            self.assertNotEqual(events[0]["event_id"], events[1]["event_id"])
            self.assertEqual(events[0]["status"], "tentative")
            self.assertEqual(current_claims(paths)[0]["status"], "corroborated")
            projection = (paths.strategy / "CLAIMS.md").read_text(encoding="utf-8")
            self.assertIn("CLM-0001", projection)
            self.assertIn("corroborated", projection)
            self.assertIn("artifacts/confirmation.json", projection)

    def test_corroborated_and_refuted_claims_require_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            with self.assertRaisesRegex(EpistemicLedgerError, "require at least one evidence"):
                record_claim(
                    paths,
                    statement="A material claim",
                    status="corroborated",
                    confidence=0.9,
                    falsifier="A preregistered replication fails",
                )

    def test_superseding_claim_marks_prior_claim_without_rewriting_history(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            first = record_claim(
                paths,
                statement="The effect is globally uniform",
                confidence=0.3,
                falsifier="Subgroup analysis shows stable heterogeneity",
            )
            second = record_claim(
                paths,
                statement="The effect is concentrated in one preregistered subgroup",
                confidence=0.6,
                falsifier="Locked subgroup confirmation is null",
                supersedes=first["claim_id"],
            )
            self.assertEqual(second["claim_id"], "CLM-0002")
            claims = current_claims(paths)
            self.assertEqual(claims[0]["effective_status"], "superseded")
            self.assertEqual(claims[0]["superseded_by"], "CLM-0002")
            self.assertEqual(len(load_claim_events(paths)), 3)

    def test_expiry_changes_effective_status_without_mutating_event(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            record_claim(
                paths,
                statement="A time-sensitive external rule remains unchanged",
                confidence=0.7,
                falsifier="The official rule page changes",
                expires_at="2020-01-01T00:00:00+00:00",
            )
            claims = current_claims(paths, now=datetime(2026, 1, 1, tzinfo=UTC))
            self.assertEqual(claims[0]["effective_status"], "expired")
            self.assertEqual(load_claim_events(paths)[0]["status"], "tentative")

    def test_tampered_event_order_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            path = paths.strategy / "CLAIMS.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "event_id": "CE-tampered",
                        "event_type": "updated",
                        "claim_id": "CLM-0001",
                        "statement": "An update without an assertion",
                        "status": "tentative",
                        "confidence": 0.2,
                        "evidence_refs": [],
                        "assumptions": [],
                        "falsifier": "A prior assertion exists",
                        "expires_at": None,
                        "source_campaign": None,
                        "recorded_by": "test",
                        "supersedes": None,
                        "recorded_at": "2026-07-16T00:00:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EpistemicLedgerError, "before it is asserted"):
                load_claim_events(paths)

    def test_refuted_claim_cannot_be_silently_revived(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            claim = record_claim(
                paths,
                statement="The effect survives locked confirmation",
                status="refuted",
                confidence=0.05,
                evidence_refs=["artifacts/locked-confirmation.json"],
                falsifier="A new preregistered measurement establishes the effect",
            )
            with self.assertRaisesRegex(EpistemicLedgerError, "cannot be updated"):
                update_claim(
                    paths,
                    claim["claim_id"],
                    status="corroborated",
                    confidence=0.9,
                    evidence_refs=["artifacts/later-result.json"],
                )
            replacement = record_claim(
                paths,
                statement="A narrower effect appears under the revised measurement contract",
                confidence=0.4,
                falsifier="The revised locked confirmation is null",
                supersedes=claim["claim_id"],
            )
            self.assertEqual(replacement["claim_id"], "CLM-0002")
            self.assertEqual(current_claims(paths)[0]["effective_status"], "superseded")

    def test_tampered_event_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            paths = make_repo(Path(raw))
            record_claim(
                paths,
                statement="A valid initial claim",
                confidence=0.2,
                falsifier="A disconfirming experiment",
                source_campaign="C-001",
            )
            path = paths.strategy / "CLAIMS.jsonl"
            prior = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            tampered = {
                **prior,
                "event_id": "CE-deadbeef",
                "event_type": "updated",
                "source_campaign": "C-999",
                "recorded_at": "2026-07-16T01:00:00+00:00",
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(tampered) + "\n")
            with self.assertRaisesRegex(EpistemicLedgerError, "immutable field"):
                load_claim_events(paths)


if __name__ == "__main__":
    unittest.main()
