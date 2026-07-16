from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .locking import lab_lock
from .models import LabPaths
from .utils import atomic_write_json, atomic_write_text, deep_merge, iso_now, read_json

PLAN_RE = re.compile(r"^RP-(\d{3,})$")
ALLOWED_STATUS = {"draft", "researching", "ready", "campaign_running", "replanning", "complete"}
PLAN_AUTHORITATIVE_FIELDS = frozenset(
    {"schema_version", "plan_id", "revision", "status", "strategy_epoch", "selected_campaign", "created_at"}
)
PLAN_STATUS_TRANSITIONS = {
    "draft": frozenset({"researching"}),
    "researching": frozenset({"ready", "replanning", "complete"}),
    "ready": frozenset({"researching", "campaign_running", "replanning", "complete"}),
    "campaign_running": frozenset({"replanning", "complete"}),
    "replanning": frozenset({"researching", "ready", "complete"}),
    "complete": frozenset(),
}
_UNSET = object()


class PlanStateConflictError(RuntimeError):
    """Raised when a caller attempts to persist a stale ResearchPlan revision."""


def list_plan_ids(paths: LabPaths) -> list[str]:
    plans = paths.research / "plans"
    if not plans.exists():
        return []
    values = [child.name for child in plans.iterdir() if child.is_dir() and PLAN_RE.match(child.name)]
    return sorted(values, key=lambda value: int(PLAN_RE.match(value).group(1)))


def next_plan_id(paths: LabPaths) -> str:
    values = [int(match.group(1)) for value in list_plan_ids(paths) if (match := PLAN_RE.match(value))]
    return f"RP-{max(values, default=0) + 1:03d}"


def create_research_plan(
    paths: LabPaths,
    *,
    user_intent: str,
    target: str | None = None,
    deadline: str | None = None,
    plan_id: str | None = None,
) -> Path:
    with lab_lock(paths, "research-plan-ids"):
        plan_id = plan_id or next_plan_id(paths)
        if not PLAN_RE.match(plan_id):
            raise ValueError("plan_id must look like RP-001")
        directory = paths.research / "plans" / plan_id
        if directory.exists():
            raise FileExistsError(f"ResearchPlan {plan_id} already exists")
        directory.mkdir(parents=True)
        (directory / "evidence").mkdir()
        now = iso_now()
        state = {
            "schema_version": 1,
            "plan_id": plan_id,
            "revision": 0,
            "status": "draft",
            "strategy_epoch": 1,
            "target": target,
            "deadline": deadline,
            "current_action": "Preserve intent, inspect current state, and build the first Evidence Pack",
            "selected_campaign": None,
            "consultation_ids": [],
            "created_at": now,
            "updated_at": now,
        }
        atomic_write_json(directory / "STATE.json", state)
        atomic_write_text(directory / "PLAN.md", render_plan_markdown(state, user_intent))
        atomic_write_text(
            directory / "evidence" / "README.md",
            "# Evidence Pack\n\nStore dated, reproducible Planner evidence here. Separate observations, inferences, assumptions, and external reports.\n",
        )
        atomic_write_text(
            paths.research / "USER_INTENT.md", "# Original human intent\n\n" + user_intent.strip() + "\n"
        )
        return directory


def _validate_expected_revision(state: dict[str, Any], expected_revision: int | None) -> None:
    if expected_revision is None:
        return
    current = state.get("revision", 0)
    if isinstance(current, bool) or not isinstance(current, int) or current < 0:
        raise PlanStateConflictError("Persisted ResearchPlan revision is invalid")
    if expected_revision != current:
        raise PlanStateConflictError(
            f"ResearchPlan revision conflict: expected {expected_revision}, current {current}"
        )


def _persist_plan_state(
    directory: Path,
    state: dict[str, Any],
    *,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    persisted = read_json(directory / "STATE.json", default={})
    if not isinstance(persisted, dict) or not persisted:
        raise FileNotFoundError(f"Unknown ResearchPlan {directory.name}")
    _validate_expected_revision(persisted, expected_revision)
    revision = persisted.get("revision", 0)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise PlanStateConflictError("Persisted ResearchPlan revision is invalid")
    state["revision"] = revision + 1
    state["updated_at"] = iso_now()
    atomic_write_json(directory / "STATE.json", state)
    return state


def _validate_selected_campaign(paths: LabPaths, selected_campaign: Any) -> None:
    if selected_campaign is None:
        return
    if not isinstance(selected_campaign, str) or not selected_campaign:
        raise ValueError("selected_campaign must be a Campaign ID or null")
    if not (paths.campaigns / selected_campaign / "CONTRACT.json").exists():
        raise FileNotFoundError(f"selected_campaign references unknown Campaign {selected_campaign}")


def update_research_plan(
    paths: LabPaths,
    plan_id: str,
    patch: dict[str, Any],
    *,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Persist non-lifecycle Planner observations using optimistic concurrency."""

    if not isinstance(patch, dict):
        raise ValueError("ResearchPlan checkpoint patch must be an object")
    forbidden = sorted(set(patch) & PLAN_AUTHORITATIVE_FIELDS)
    if forbidden:
        raise ValueError(
            "ResearchPlan checkpoint cannot modify authoritative field(s): " + ", ".join(forbidden)
        )
    directory = paths.research / "plans" / plan_id
    with lab_lock(paths, f"research-plan-{plan_id}"):
        state = read_json(directory / "STATE.json", default={})
        if not state:
            raise FileNotFoundError(f"Unknown ResearchPlan {plan_id}")
        updated = deep_merge(state, patch)
        consultations = updated.get("consultation_ids", [])
        if not isinstance(consultations, list) or not all(isinstance(item, str) for item in consultations):
            raise ValueError("consultation_ids must be an array of strings")
        return _persist_plan_state(directory, updated, expected_revision=expected_revision)


def transition_research_plan(
    paths: LabPaths,
    plan_id: str,
    *,
    status: str,
    selected_campaign: str | None | object = _UNSET,
    current_action: str | None = None,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    """Move a ResearchPlan through its explicit lifecycle state machine."""

    if status not in ALLOWED_STATUS:
        raise ValueError(f"status must be one of {sorted(ALLOWED_STATUS)}")
    if current_action is not None and (not isinstance(current_action, str) or not current_action.strip()):
        raise ValueError("current_action must be non-empty when provided")
    directory = paths.research / "plans" / plan_id
    with lab_lock(paths, f"research-plan-{plan_id}"):
        state = read_json(directory / "STATE.json", default={})
        if not state:
            raise FileNotFoundError(f"Unknown ResearchPlan {plan_id}")
        current_status = state.get("status")
        if current_status not in ALLOWED_STATUS:
            raise ValueError(f"ResearchPlan {plan_id} has unsupported status {current_status!r}")
        if status != current_status and status not in PLAN_STATUS_TRANSITIONS[str(current_status)]:
            raise ValueError(f"ResearchPlan cannot transition from {current_status!r} to {status!r}")

        updated = dict(state)
        if selected_campaign is not _UNSET:
            _validate_selected_campaign(paths, selected_campaign)
            updated["selected_campaign"] = selected_campaign
        if status == "campaign_running":
            _validate_selected_campaign(paths, updated.get("selected_campaign"))
            if not updated.get("selected_campaign"):
                raise ValueError("campaign_running requires selected_campaign")
        if status == "replanning" and current_status != "replanning":
            epoch = updated.get("strategy_epoch", 1)
            if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 1:
                raise ValueError("strategy_epoch must be a positive integer")
            updated["strategy_epoch"] = epoch + 1
        updated["status"] = status
        if current_action is not None:
            updated["current_action"] = current_action.strip()
        return _persist_plan_state(directory, updated, expected_revision=expected_revision)


def link_campaign(
    paths: LabPaths,
    plan_id: str,
    campaign_id: str,
    *,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    return transition_research_plan(
        paths,
        plan_id,
        status="campaign_running",
        selected_campaign=campaign_id,
        current_action=f"Campaign {campaign_id} is executing; synthesize its Handoff when complete",
        expected_revision=expected_revision,
    )


def render_plan_markdown(state: dict[str, Any], user_intent: str) -> str:
    return f"""# ResearchPlan {state["plan_id"]}

Status: **{state["status"]}**

Strategy epoch: **{state["strategy_epoch"]}**

Target: {state.get("target") or "Not specified"}

Deadline: {state.get("deadline") or "Not specified"}

## Original mission

{user_intent.strip()}

## Current state and constraints

Planner must inspect the official rules/current state, available compute, prior evidence, and time horizon.

## Data-generating process and EDA

Pending reproducible evidence.

## Evaluation, baseline, and compute profile

Pending reproducible evidence.

## Broad research landscape

### Primary

### Hedge

### Wildcard

### Dormant / rejected

## Independent consultations

First responses must be independent and evidence-linked.

## Selected Campaign and why now

Not selected yet.

## Strongest counterargument

Not recorded yet.

## Evidence that would reverse the decision

Not recorded yet.

## Human brief

Research planning has started. No long GPU campaign should begin until a ready Campaign Contract exists.
"""
