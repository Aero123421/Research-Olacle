from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import LabPaths
from .schema import validate_campaign_contract, validate_campaign_handoff, validate_or_raise
from .utils import atomic_write_json, atomic_write_text, deep_merge, iso_now, read_json, safe_relpath

CAMPAIGN_PATTERN = re.compile(r"^C-(\d{3,})$")


def list_campaign_ids(paths: LabPaths) -> list[str]:
    if not paths.campaigns.exists():
        return []
    return sorted(
        child.name
        for child in paths.campaigns.iterdir()
        if child.is_dir() and CAMPAIGN_PATTERN.match(child.name)
    )


def next_campaign_id(paths: LabPaths) -> str:
    numbers = [
        int(match.group(1)) for value in list_campaign_ids(paths) if (match := CAMPAIGN_PATTERN.match(value))
    ]
    return f"C-{(max(numbers, default=0) + 1):03d}"


def default_contract(campaign_id: str, title: str, goal: str) -> dict[str, Any]:
    """Return an intentionally draft contract that Planner must complete."""

    return {
        "schema_version": 1,
        "contract_status": "draft",
        "campaign_id": campaign_id,
        "title": title,
        "mission": "See research/MISSION.md",
        "goal": goal,
        "why_now": "Planner must replace this with an evidence-based rationale.",
        "decision_to_unlock": "Planner must state the strategic decision unlocked by this campaign.",
        "scope": {
            "in": ["Planner must define the research space that belongs to this campaign."],
            "out": ["Unrelated infrastructure and other campaign branches."],
        },
        "success_conditions": ["Planner must define a measurable, evidence-backed success condition."],
        "withdrawal_conditions": ["Planner must define a measurable stop condition."],
        "budget": {"wall_hours": 12.0, "gpu_hours": 6.0, "paid_compute_jpy": 0.0},
        "checkpoint_policy": {
            "budget_fractions": [0.25, 0.5, 0.8],
            "events": [
                "phase_change",
                "material_evidence",
                "strategy_conflict",
                "before_pause",
                "before_context_compaction",
            ],
        },
        "evaluation_contract": "research/protocols/EVALUATION_CONTRACT.md",
        "fixed_constraints": [
            "Do not change the mission, evaluation contract, or resource budget without replanning.",
            "Keep competition rules and data-use constraints intact.",
        ],
        "forbidden_detours": [
            "Building generic infrastructure that cannot pay back inside this campaign.",
            "Deep dives that cannot change a stated decision.",
        ],
        "evidence_inputs": ["research/strategy/EVIDENCE_INDEX.md"],
        "required_outputs": [
            "Campaign report",
            "Planner handoff",
            "Experiment registry entries",
            "Reproducible artifacts and commit references",
        ],
        "owner": {"runtime": "codex-goal", "model": "gpt-5.6-sol", "effort": "high"},
        "created_at": iso_now(),
    }


def _initial_state(campaign_id: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "status": "draft",
        "health": "on_track",
        "phase": "contract",
        "research_signal": "unknown",
        "current_action": "Complete and validate the Campaign Contract",
        "next_actions": ["Build executor context pack", "Start GPT-5.6 Sol High Goal Mode"],
        "progress": {"completed_milestones": 0, "total_milestones": 0},
        "resources": {"wall_hours_used": 0.0, "gpu_hours_used": 0.0, "cost_jpy": 0.0},
        "budget_fraction_used": 0.0,
        "budget_status": "within_budget",
        "forecast": {"finish_low": None, "finish_high": None, "hard_stop": None},
        "last_checkpoint_at": iso_now(),
    }


def create_campaign(
    paths: LabPaths,
    *,
    title: str,
    goal: str,
    contract: dict[str, Any] | None = None,
    campaign_id: str | None = None,
) -> Path:
    campaign_id = campaign_id or next_campaign_id(paths)
    if not CAMPAIGN_PATTERN.match(campaign_id):
        raise ValueError("campaign_id must look like C-001")
    directory = paths.campaigns / campaign_id
    if directory.exists():
        raise FileExistsError(f"Campaign {campaign_id} already exists")
    directory.mkdir(parents=True)
    value = dict(contract) if contract else default_contract(campaign_id, title, goal)
    value["campaign_id"] = campaign_id
    value.setdefault("title", title)
    value.setdefault("goal", goal)
    state = _initial_state(campaign_id)
    atomic_write_json(directory / "CONTRACT.json", value)
    atomic_write_json(directory / "STATE.json", state)
    atomic_write_text(directory / "STATE.md", render_state_markdown(state, value))
    atomic_write_text(directory / "HYPOTHESES.md", "# Hypotheses\n\nNo hypotheses registered yet.\n")
    atomic_write_text(directory / "FINDINGS.md", "# Confirmed findings\n\nNo confirmed findings yet.\n")
    atomic_write_text(directory / "REPORT.md", "# Campaign report\n\nPending.\n")
    atomic_write_text(directory / "HANDOFF.md", "# Planner handoff\n\nPending.\n")
    atomic_write_text(directory / "GOAL_PROMPT.md", render_goal_prompt(value))
    return directory


def validate_contract_file(path: Path) -> list[str]:
    value = read_json(path)
    return [str(issue) for issue in validate_campaign_contract(value, require_ready=True)]


def finalize_campaign_contract(paths: LabPaths, campaign_id: str) -> dict[str, Any]:
    """Mark a completed Planner contract ready only after strict validation."""

    directory = paths.campaigns / campaign_id
    contract_path = directory / "CONTRACT.json"
    contract = read_json(contract_path, default={})
    if not contract:
        raise FileNotFoundError(f"Unknown campaign {campaign_id}")
    candidate = dict(contract)
    candidate["contract_status"] = "ready"
    candidate["finalized_at"] = iso_now()
    validate_or_raise(candidate, lambda value: validate_campaign_contract(value, require_ready=True))
    atomic_write_json(contract_path, candidate)
    state = read_json(directory / "STATE.json", default={})
    state = deep_merge(
        state,
        {
            "status": "ready",
            "phase": "contract",
            "current_action": "Build bounded Executor context and launch fresh Goal Mode session",
            "last_checkpoint_at": iso_now(),
        },
    )
    _persist_state(directory, state, candidate)
    atomic_write_text(directory / "GOAL_PROMPT.md", render_goal_prompt(candidate))
    return candidate


def activate_campaign(paths: LabPaths, campaign_id: str) -> dict[str, Any]:
    directory = paths.campaigns / campaign_id
    contract = read_json(directory / "CONTRACT.json")
    validate_or_raise(contract, lambda value: validate_campaign_contract(value, require_ready=True))
    state = read_json(directory / "STATE.json", default={})
    if state.get("status") == "completed":
        raise ValueError(f"Campaign {campaign_id} is already completed")
    state = deep_merge(
        state,
        {
            "status": "ready",
            "phase": "context_pack",
            "current_action": "Prepare bounded executor context",
            "last_checkpoint_at": iso_now(),
        },
    )
    _persist_state(directory, state, contract)
    atomic_write_text(directory / "GOAL_PROMPT.md", render_goal_prompt(contract))
    return state


def update_campaign_state(paths: LabPaths, campaign_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    directory = paths.campaigns / campaign_id
    state_path = directory / "STATE.json"
    state = read_json(state_path, default={})
    contract = read_json(directory / "CONTRACT.json", default={})
    if not state:
        raise FileNotFoundError(f"Missing state for {campaign_id}")
    for key in ("campaign_id", "schema_version"):
        if key in patch and patch[key] != state.get(key):
            raise ValueError(f"Cannot change {key}")
    updated = deep_merge(state, patch)
    _validate_resource_state(updated)
    _apply_budget_status(updated, contract)
    updated["last_checkpoint_at"] = iso_now()
    _persist_state(directory, updated, contract)
    return updated


def complete_campaign(paths: LabPaths, campaign_id: str, handoff: dict[str, Any]) -> dict[str, Any]:
    directory = paths.campaigns / campaign_id
    if not directory.exists():
        raise FileNotFoundError(f"Unknown campaign {campaign_id}")
    handoff = dict(handoff)
    handoff["campaign_id"] = campaign_id
    validate_or_raise(handoff, validate_campaign_handoff)
    for index, evidence in enumerate(handoff.get("evidence", [])):
        artifact = evidence.get("artifact") if isinstance(evidence, dict) else None
        if not isinstance(artifact, str):
            continue
        artifact_path = paths.root / artifact
        safe_relpath(artifact_path, paths.root)
        if not artifact_path.exists():
            raise FileNotFoundError(
                f"Handoff evidence artifact does not exist: evidence[{index}] {artifact!r}"
            )
    existing = read_json(directory / "HANDOFF.json", default=None)
    if existing is not None and existing != handoff:
        raise ValueError(f"Campaign {campaign_id} already has a different completed handoff")
    atomic_write_json(directory / "HANDOFF.json", handoff)
    atomic_write_text(directory / "HANDOFF.md", render_handoff_markdown(handoff))
    state = read_json(directory / "STATE.json", default={})
    actual = handoff["resources_actual"]
    state = deep_merge(
        state,
        {
            "status": "completed",
            "phase": "handoff",
            "current_action": "Research Planner must synthesize the handoff",
            "next_actions": [
                "Resume or create Research Planner session",
                "Update strategy memory",
                "Select next campaign",
            ],
            "outcome": handoff["outcome"],
            "resources": {
                "wall_hours_used": actual["wall_hours"],
                "gpu_hours_used": actual["gpu_hours"],
                "cost_jpy": actual["cost_jpy"],
            },
            "last_checkpoint_at": iso_now(),
        },
    )
    contract = read_json(directory / "CONTRACT.json", default={})
    _apply_budget_status(state, contract)
    _persist_state(directory, state, contract)
    return state


def _validate_resource_state(state: dict[str, Any]) -> None:
    resources = state.get("resources", {})
    if not isinstance(resources, dict):
        raise ValueError("resources must be an object")
    for key in ("wall_hours_used", "gpu_hours_used", "cost_jpy"):
        value = resources.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
            raise ValueError(f"resources.{key} must be a non-negative number")


def _apply_budget_status(state: dict[str, Any], contract: dict[str, Any]) -> None:
    resources = state.get("resources", {})
    budget = contract.get("budget", {})
    ratios: list[float] = []
    for used_key, budget_key in (
        ("wall_hours_used", "wall_hours"),
        ("gpu_hours_used", "gpu_hours"),
        ("cost_jpy", "paid_compute_jpy"),
    ):
        used = float(resources.get(used_key, 0) or 0)
        allowed = float(budget.get(budget_key, 0) or 0)
        if allowed > 0:
            ratios.append(used / allowed)
        elif used > 0:
            ratios.append(float("inf"))
    fraction = max(ratios, default=0.0)
    state["budget_fraction_used"] = fraction if fraction != float("inf") else 999.0
    if fraction >= 1:
        state["budget_status"] = "exhausted"
        state["health"] = "at_risk"
        state["withdrawal_triggered"] = "resource_budget_exhausted"
    elif fraction >= 0.8:
        state["budget_status"] = "finalization_only"
    elif fraction >= 0.5:
        state["budget_status"] = "midpoint_review"
    elif fraction >= 0.25:
        state["budget_status"] = "early_review"
    else:
        state["budget_status"] = "within_budget"


def _persist_state(directory: Path, state: dict[str, Any], contract: dict[str, Any]) -> None:
    atomic_write_json(directory / "STATE.json", state)
    atomic_write_text(directory / "STATE.md", render_state_markdown(state, contract))


def render_state_markdown(state: dict[str, Any], contract: dict[str, Any]) -> str:
    progress = state.get("progress", {})
    resources = state.get("resources", {})
    budget = contract.get("budget", {})
    forecast = state.get("forecast", {})
    next_actions = "\n".join(f"- {item}" for item in state.get("next_actions", [])) or "- None recorded"
    return f"""# Current Campaign State — {state.get("campaign_id", "unknown")}

- Status: **{state.get("status", "unknown")}**
- Health: **{state.get("health", "unknown")}**
- Phase: **{state.get("phase", "unknown")}**
- Research signal: **{state.get("research_signal", "unknown")}**
- Current action: {state.get("current_action", "")}
- Milestones: {progress.get("completed_milestones", 0)} / {progress.get("total_milestones", 0)}
- Wall time: {resources.get("wall_hours_used", 0)} / {budget.get("wall_hours", 0)} h
- GPU time: {resources.get("gpu_hours_used", 0)} / {budget.get("gpu_hours", 0)} h
- Cost: JPY {resources.get("cost_jpy", 0)} / {budget.get("paid_compute_jpy", 0)}
- Budget gate: **{state.get("budget_status", "unknown")}**
- Forecast: {forecast.get("finish_low")} – {forecast.get("finish_high")}
- Hard stop: {forecast.get("hard_stop")}
- Last checkpoint: `{state.get("last_checkpoint_at", "unknown")}`

## Next actions

{next_actions}

This file is regenerated from `STATE.json`; edit state through
`researchctl campaign checkpoint` so machine and human views stay consistent.
"""


def render_goal_prompt(contract: dict[str, Any]) -> str:
    campaign_id = contract.get("campaign_id", "C-XXX")
    success = "\n".join(f"- {item}" for item in contract.get("success_conditions", []))
    withdrawal = "\n".join(f"- {item}" for item in contract.get("withdrawal_conditions", []))
    fixed = "\n".join(f"- {item}" for item in contract.get("fixed_constraints", []))
    forbidden = "\n".join(f"- {item}" for item in contract.get("forbidden_detours", []))
    budget = contract.get("budget", {})
    return f"""# Goal Mode launch prompt — {campaign_id}

Open a fresh Codex research session, select **GPT-5.6 Sol High**, load the
`research-executor` Skill, and start this campaign with `/goal`.

```text
/goal

Pursue the research campaign defined in
`research/campaigns/{campaign_id}/CONTRACT.json` until a success, withdrawal,
strategy-conflict, invalidation, or resource-budget condition is reached.

Read only the bounded `CONTEXT_PACK.md` and files explicitly referenced from it.
Persist state with `context-checkpoint`; never rely on the conversation as the
only copy of research state.

Goal:
{contract.get("goal", "")}

Decision this campaign must unlock:
{contract.get("decision_to_unlock", "")}

Success conditions:
{success}

Withdrawal conditions:
{withdrawal}

Resource budget:
- Wall clock: {budget.get("wall_hours", 0)} hours
- GPU: {budget.get("gpu_hours", 0)} hours
- Paid compute: JPY {budget.get("paid_compute_jpy", 0)}

Fixed constraints:
{fixed}

Forbidden detours:
{forbidden}

You own implementation, hypothesis generation, experiment ordering, evidence
analysis, and bounded consultation with ChatGPT Pro, Claude Code, and Grok
Build. You may not change the Mission, evaluation contract, Campaign boundary,
or resource limits. Return only evidence-backed Handoff state to Planner; do not
return the full transcript or hidden reasoning.
```
"""


def render_handoff_markdown(value: dict[str, Any]) -> str:
    def bullets(key: str) -> str:
        items = value.get(key, [])
        return "\n".join(f"- {item}" for item in items) or "- None"

    evidence_rows = []
    for item in value.get("evidence", []):
        if isinstance(item, dict):
            evidence_rows.append(
                f"- **{item.get('claim', 'Evidence')}** — `{item.get('artifact', '')}` "
                f"at `{item.get('commit', '')}`"
            )
    actual = value.get("resources_actual", {})
    return f"""# Planner handoff — {value.get("campaign_id")}

Outcome: **{value.get("outcome")}**

## Summary

{value.get("summary")}

## Evidence

{chr(10).join(evidence_rows) or "- None"}

## Confirmed findings

{bullets("confirmed_findings")}

## Rejected hypotheses

{bullets("rejected_hypotheses")}

## Unexpected observations

{bullets("unexpected_observations")}

## Strategic implications

{bullets("strategic_implications")}

## Executor recommendations (not decisions)

{bullets("executor_recommendations")}

## Resources actually used

- Wall: {actual.get("wall_hours", 0)} h
- GPU: {actual.get("gpu_hours", 0)} h
- Cost: JPY {actual.get("cost_jpy", 0)}

## Limitations

{bullets("limitations")}
"""
