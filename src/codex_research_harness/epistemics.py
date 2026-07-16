from __future__ import annotations

import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .locking import lab_lock
from .models import LabPaths
from .utils import atomic_write_text, ensure_parent, iso_now

CLAIM_ID_RE = re.compile(r"^CLM-(\d{4,})$")
EVENT_ID_RE = re.compile(r"^CE-[a-f0-9]+$")
CLAIM_STATUSES = frozenset({"tentative", "corroborated", "refuted", "superseded"})
TERMINAL_CLAIM_STATUSES = frozenset({"refuted", "superseded"})
CLAIM_STATUS_TRANSITIONS = {
    "tentative": frozenset({"tentative", "corroborated", "refuted", "superseded"}),
    "corroborated": frozenset({"tentative", "corroborated", "refuted", "superseded"}),
    "refuted": frozenset({"superseded"}),
    "superseded": frozenset(),
}


class EpistemicLedgerError(ValueError):
    """Raised when an epistemic claim event is malformed or inconsistent."""


def claim_ledger_path(paths: LabPaths) -> Path:
    return paths.strategy / "CLAIMS.jsonl"


def claim_projection_path(paths: LabPaths) -> Path:
    return paths.strategy / "CLAIMS.md"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EpistemicLedgerError(f"Invalid ISO timestamp {value!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def load_claim_events(paths: LabPaths) -> list[dict[str, Any]]:
    path = claim_ledger_path(paths)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    seen_event_ids: set[str] = set()
    latest_by_claim: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EpistemicLedgerError(
                f"Malformed epistemic ledger JSON at line {line_number}: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise EpistemicLedgerError(
                f"Malformed epistemic ledger event at line {line_number}: expected object"
            )
        event_id = value.get("event_id")
        if isinstance(event_id, str) and event_id in seen_event_ids:
            raise EpistemicLedgerError(f"Duplicate epistemic event_id {event_id!r} at line {line_number}")
        event_type = value.get("event_type")
        claim_id = value.get("claim_id")
        try:
            if event_type == "asserted":
                if isinstance(claim_id, str) and claim_id in seen_claim_ids:
                    raise EpistemicLedgerError(f"Claim {claim_id} is asserted more than once")
                _validate_claim_event(value, existing_ids=seen_claim_ids)
                seen_claim_ids.add(str(claim_id))
            elif event_type == "updated":
                if not isinstance(claim_id, str) or claim_id not in seen_claim_ids:
                    raise EpistemicLedgerError(f"Update references claim {claim_id!r} before it is asserted")
                _validate_claim_event(value, existing_ids=seen_claim_ids)
                previous = latest_by_claim[claim_id]
                for immutable_key in ("claim_id", "source_campaign", "supersedes"):
                    if value.get(immutable_key) != previous.get(immutable_key):
                        raise EpistemicLedgerError(f"updated event changes immutable field {immutable_key!r}")
                previous_status = str(previous.get("status"))
                next_status = str(value.get("status"))
                if next_status not in CLAIM_STATUS_TRANSITIONS.get(previous_status, frozenset()):
                    raise EpistemicLedgerError(
                        f"claim cannot transition from {previous_status!r} to {next_status!r}"
                    )
                previous_time = _parse_iso(previous.get("recorded_at"))
                current_time = _parse_iso(value.get("recorded_at"))
                if previous_time and current_time and current_time < previous_time:
                    raise EpistemicLedgerError("updated event predates the prior claim event")
            else:
                _validate_claim_event(value, existing_ids=seen_claim_ids)
        except EpistemicLedgerError as exc:
            raise EpistemicLedgerError(
                f"Invalid epistemic ledger event at line {line_number}: {exc}"
            ) from exc
        seen_event_ids.add(str(event_id))
        latest_by_claim[str(claim_id)] = value
        events.append(value)
    return events


def _claim_number(claim_id: str) -> int:
    match = CLAIM_ID_RE.match(claim_id)
    if not match:
        raise EpistemicLedgerError(f"Invalid claim_id {claim_id!r}")
    return int(match.group(1))


def next_claim_id(events: list[dict[str, Any]]) -> str:
    numbers = [
        _claim_number(str(event["claim_id"]))
        for event in events
        if isinstance(event.get("claim_id"), str) and CLAIM_ID_RE.match(str(event["claim_id"]))
    ]
    return f"CLM-{max(numbers, default=0) + 1:04d}"


def _normalize_string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise EpistemicLedgerError(f"{field} must be an array of non-empty strings")
    normalized = [item.strip() for item in value]
    if field == "evidence_refs" and len(normalized) != len(set(normalized)):
        raise EpistemicLedgerError("evidence_refs must not contain duplicates")
    return normalized


def _validate_claim_event(event: dict[str, Any], *, existing_ids: set[str]) -> None:
    if event.get("schema_version") != 1:
        raise EpistemicLedgerError("schema_version must be 1")
    claim_id = event.get("claim_id")
    if not isinstance(claim_id, str) or not CLAIM_ID_RE.match(claim_id):
        raise EpistemicLedgerError("claim_id must look like CLM-0001")
    for key in ("event_id", "event_type", "statement", "falsifier", "recorded_by", "recorded_at"):
        value = event.get(key)
        if not isinstance(value, str) or not value.strip():
            raise EpistemicLedgerError(f"{key} must be a non-empty string")
    if not EVENT_ID_RE.match(str(event.get("event_id"))):
        raise EpistemicLedgerError("event_id must look like CE-<lowercase-hex>")
    if event.get("event_type") not in {"asserted", "updated"}:
        raise EpistemicLedgerError("event_type must be asserted or updated")
    _parse_iso(event.get("recorded_at"))
    status = event.get("status")
    if status not in CLAIM_STATUSES:
        raise EpistemicLedgerError(f"status must be one of {sorted(CLAIM_STATUSES)}")
    confidence = event.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, int | float)
        or not 0 <= float(confidence) <= 1
    ):
        raise EpistemicLedgerError("confidence must be a number between 0 and 1")
    evidence_refs = _normalize_string_list(event.get("evidence_refs"), "evidence_refs")
    _normalize_string_list(event.get("assumptions"), "assumptions")
    if status in {"corroborated", "refuted"} and not evidence_refs:
        raise EpistemicLedgerError(f"{status} claims require at least one evidence reference")
    expires_at = event.get("expires_at")
    if expires_at is not None:
        if not isinstance(expires_at, str):
            raise EpistemicLedgerError("expires_at must be an ISO timestamp or null")
        _parse_iso(expires_at)
    source_campaign = event.get("source_campaign")
    if source_campaign is not None and (
        not isinstance(source_campaign, str) or not re.match(r"^C-\d{3,}$", source_campaign)
    ):
        raise EpistemicLedgerError("source_campaign must look like C-001 or be null")
    supersedes = event.get("supersedes")
    if supersedes is not None:
        if not isinstance(supersedes, str) or not CLAIM_ID_RE.match(supersedes):
            raise EpistemicLedgerError("supersedes must look like CLM-0001 or be null")
        if supersedes == claim_id:
            raise EpistemicLedgerError("A claim cannot supersede itself")
        if supersedes not in existing_ids:
            raise EpistemicLedgerError(f"supersedes references unknown claim {supersedes}")
    if status == "superseded":
        if event.get("event_type") == "asserted":
            raise EpistemicLedgerError("A claim cannot be asserted in superseded status")
        superseded_by = event.get("superseded_by")
        if not isinstance(superseded_by, str) or not CLAIM_ID_RE.match(superseded_by):
            raise EpistemicLedgerError("superseded claims require superseded_by")
        if superseded_by == claim_id or superseded_by not in existing_ids:
            raise EpistemicLedgerError("superseded_by must reference a different known claim")


def _append_events(path: Path, events: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    encoded = "".join(
        json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events
    ).encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        offset = 0
        while offset < len(encoded):
            offset += os.write(descriptor, encoded[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def current_claims(
    paths: LabPaths,
    *,
    status: str | None = None,
    include_expired: bool = True,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if status is not None and status not in CLAIM_STATUSES | {"expired"}:
        raise EpistemicLedgerError(f"status must be one of {sorted(CLAIM_STATUSES | {'expired'})}")
    latest: dict[str, dict[str, Any]] = {}
    for event in load_claim_events(paths):
        claim_id = event.get("claim_id")
        if isinstance(claim_id, str):
            latest[claim_id] = dict(event)
    effective_now = now or datetime.now(UTC)
    values: list[dict[str, Any]] = []
    for value in latest.values():
        expiry = _parse_iso(value.get("expires_at"))
        effective_status = str(value.get("status"))
        if expiry and expiry <= effective_now and effective_status not in TERMINAL_CLAIM_STATUSES:
            effective_status = "expired"
        value["effective_status"] = effective_status
        if not include_expired and effective_status == "expired":
            continue
        if status is not None and effective_status != status:
            continue
        values.append(value)
    return sorted(values, key=lambda item: _claim_number(str(item["claim_id"])))


def _write_projection(paths: LabPaths) -> None:
    claims = current_claims(paths)
    lines = [
        "# Epistemic claim ledger",
        "",
        "This is a generated projection of the append-only `CLAIMS.jsonl` ledger.",
        "Operational state is not scientific truth: each claim records confidence,",
        "assumptions, evidence, a falsifier, and an effective status.",
        "",
    ]
    if not claims:
        lines.extend(["No claims recorded yet.", ""])
    for claim in claims:
        evidence = claim.get("evidence_refs", [])
        assumptions = claim.get("assumptions", [])
        lines.extend(
            [
                f"## {claim['claim_id']} — {claim.get('effective_status', claim.get('status'))}",
                "",
                str(claim.get("statement", "")),
                "",
                f"- Confidence: **{float(claim.get('confidence', 0)):.2f}**",
                f"- Falsifier: {claim.get('falsifier', '')}",
                f"- Source Campaign: `{claim.get('source_campaign') or 'none'}`",
                f"- Expires: `{claim.get('expires_at') or 'never'}`",
                f"- Recorded by: `{claim.get('recorded_by', '')}` at `{claim.get('recorded_at', '')}`",
                "- Evidence:",
                *([f"  - `{item}`" for item in evidence] or ["  - None linked"]),
                "- Assumptions:",
                *([f"  - {item}" for item in assumptions] or ["  - None recorded"]),
                "",
            ]
        )
    atomic_write_text(claim_projection_path(paths), "\n".join(lines).rstrip() + "\n")


def record_claim(
    paths: LabPaths,
    *,
    statement: str,
    confidence: float,
    falsifier: str,
    status: str = "tentative",
    evidence_refs: list[str] | None = None,
    assumptions: list[str] | None = None,
    expires_at: str | None = None,
    source_campaign: str | None = None,
    recorded_by: str = "research-planner",
    supersedes: str | None = None,
    claim_id: str | None = None,
) -> dict[str, Any]:
    with lab_lock(paths, "epistemic-claims"):
        events = load_claim_events(paths)
        existing_ids = {str(event["claim_id"]) for event in events if isinstance(event.get("claim_id"), str)}
        actual_claim_id = claim_id or next_claim_id(events)
        if actual_claim_id in existing_ids:
            raise EpistemicLedgerError(f"Claim {actual_claim_id} already exists")
        event = {
            "schema_version": 1,
            "event_id": f"CE-{uuid.uuid4().hex}",
            "event_type": "asserted",
            "claim_id": actual_claim_id,
            "statement": statement.strip() if isinstance(statement, str) else statement,
            "status": status,
            "confidence": float(confidence),
            "evidence_refs": _normalize_string_list(evidence_refs, "evidence_refs"),
            "assumptions": _normalize_string_list(assumptions, "assumptions"),
            "falsifier": falsifier.strip() if isinstance(falsifier, str) else falsifier,
            "expires_at": expires_at,
            "source_campaign": source_campaign,
            "recorded_by": recorded_by.strip() if isinstance(recorded_by, str) else recorded_by,
            "supersedes": supersedes,
            "recorded_at": iso_now(),
        }
        if status == "superseded":
            raise EpistemicLedgerError("A new claim cannot begin in superseded status")
        _validate_claim_event(event, existing_ids=existing_ids)
        pending = [event]
        if supersedes is not None:
            latest_by_id: dict[str, dict[str, Any]] = {}
            for prior_event in events:
                if isinstance(prior_event.get("claim_id"), str):
                    latest_by_id[str(prior_event["claim_id"])] = prior_event
            previous = latest_by_id[supersedes]
            if previous.get("status") == "superseded":
                raise EpistemicLedgerError(f"Claim {supersedes} is already superseded")
            superseded_event = {
                **previous,
                "schema_version": 1,
                "event_id": f"CE-{uuid.uuid4().hex}",
                "event_type": "updated",
                "status": "superseded",
                "superseded_by": actual_claim_id,
                "recorded_by": event["recorded_by"],
                "recorded_at": event["recorded_at"],
            }
            _validate_claim_event(
                superseded_event,
                existing_ids=existing_ids | {actual_claim_id},
            )
            # Assert the replacement before marking the prior claim superseded.
            # A crash after the first complete line leaves two live claims rather
            # than a claim pointing to a replacement that does not yet exist.
            pending = [event, superseded_event]
        _append_events(claim_ledger_path(paths), pending)
        _write_projection(paths)
        return dict(event, effective_status=event["status"])


def update_claim(
    paths: LabPaths,
    claim_id: str,
    *,
    status: str | None = None,
    confidence: float | None = None,
    statement: str | None = None,
    evidence_refs: list[str] | None = None,
    assumptions: list[str] | None = None,
    falsifier: str | None = None,
    expires_at: str | None | object = ...,
    recorded_by: str = "research-planner",
) -> dict[str, Any]:
    with lab_lock(paths, "epistemic-claims"):
        events = load_claim_events(paths)
        latest_by_id: dict[str, dict[str, Any]] = {}
        for event in events:
            if isinstance(event.get("claim_id"), str):
                latest_by_id[str(event["claim_id"])] = event
        previous = latest_by_id.get(claim_id)
        if not previous:
            raise FileNotFoundError(f"Unknown epistemic claim {claim_id}")
        if previous.get("status") in TERMINAL_CLAIM_STATUSES:
            raise EpistemicLedgerError(
                f"Claim {claim_id} is {previous.get('status')} and cannot be updated; "
                "record a replacement claim with supersedes instead"
            )
        if status == "superseded":
            raise EpistemicLedgerError("Use record_claim(..., supersedes=claim_id) to supersede a claim")

        combined_evidence = list(previous.get("evidence_refs", []))
        if evidence_refs is not None:
            for item in _normalize_string_list(evidence_refs, "evidence_refs"):
                if item not in combined_evidence:
                    combined_evidence.append(item)
        combined_assumptions = (
            _normalize_string_list(assumptions, "assumptions")
            if assumptions is not None
            else list(previous.get("assumptions", []))
        )
        event = {
            **previous,
            "schema_version": 1,
            "event_id": f"CE-{uuid.uuid4().hex}",
            "event_type": "updated",
            "statement": statement.strip() if isinstance(statement, str) else previous.get("statement"),
            "status": status or previous.get("status"),
            "confidence": float(confidence) if confidence is not None else previous.get("confidence"),
            "evidence_refs": combined_evidence,
            "assumptions": combined_assumptions,
            "falsifier": falsifier.strip() if isinstance(falsifier, str) else previous.get("falsifier"),
            "expires_at": previous.get("expires_at") if expires_at is ... else expires_at,
            "recorded_by": recorded_by.strip() if isinstance(recorded_by, str) else recorded_by,
            "recorded_at": iso_now(),
        }
        existing_ids = set(latest_by_id)
        _validate_claim_event(event, existing_ids=existing_ids)
        _append_events(claim_ledger_path(paths), [event])
        _write_projection(paths)
        return dict(event, effective_status=event["status"])
