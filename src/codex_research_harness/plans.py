from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import LabPaths
from .utils import atomic_write_json, atomic_write_text, deep_merge, iso_now, read_json

PLAN_RE = re.compile(r"^RP-(\d{3,})$")
ALLOWED_STATUS = {"draft", "researching", "ready", "campaign_running", "replanning", "complete"}


def list_plan_ids(paths: LabPaths) -> list[str]:
    plans = paths.research / "plans"
    if not plans.exists():
        return []
    return sorted(child.name for child in plans.iterdir() if child.is_dir() and PLAN_RE.match(child.name))


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


def update_research_plan(paths: LabPaths, plan_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    directory = paths.research / "plans" / plan_id
    state = read_json(directory / "STATE.json", default={})
    if not state:
        raise FileNotFoundError(f"Unknown ResearchPlan {plan_id}")
    for key in ("schema_version", "plan_id", "created_at"):
        if key in patch and patch[key] != state.get(key):
            raise ValueError(f"Cannot change {key}")
    updated = deep_merge(state, patch)
    if updated.get("status") not in ALLOWED_STATUS:
        raise ValueError(f"status must be one of {sorted(ALLOWED_STATUS)}")
    selected = updated.get("selected_campaign")
    if selected and not (paths.campaigns / selected / "CONTRACT.json").exists():
        raise FileNotFoundError(f"selected_campaign references unknown Campaign {selected}")
    updated["updated_at"] = iso_now()
    atomic_write_json(directory / "STATE.json", updated)
    return updated


def link_campaign(paths: LabPaths, plan_id: str, campaign_id: str) -> dict[str, Any]:
    return update_research_plan(
        paths,
        plan_id,
        {
            "status": "campaign_running",
            "selected_campaign": campaign_id,
            "current_action": f"Campaign {campaign_id} is executing; synthesize its Handoff when complete",
        },
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
