from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .models import LabPaths
from .plans import list_plan_ids
from .utils import atomic_write_json, atomic_write_text, iso_now, read_json

LoopAction = Literal[
    "start_planner",
    "run_planner",
    "start_executor",
    "monitor_executor",
    "resume_planner",
    "mission_complete",
    "repair_state",
]


@dataclass(frozen=True)
class LoopDecision:
    action: LoopAction
    reason: str
    plan_id: str | None = None
    campaign_id: str | None = None
    plan_status: str | None = None
    campaign_status: str | None = None
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "action": self.action,
            "reason": self.reason,
            "plan_id": self.plan_id,
            "campaign_id": self.campaign_id,
            "plan_status": self.plan_status,
            "campaign_status": self.campaign_status,
            "generated_at": self.generated_at or iso_now(),
        }


def _decision(
    action: LoopAction,
    reason: str,
    *,
    plan_id: str | None = None,
    campaign_id: str | None = None,
    plan_status: str | None = None,
    campaign_status: str | None = None,
) -> LoopDecision:
    return LoopDecision(
        action=action,
        reason=reason,
        plan_id=plan_id,
        campaign_id=campaign_id,
        plan_status=plan_status,
        campaign_status=campaign_status,
        generated_at=iso_now(),
    )


def inspect_research_loop(paths: LabPaths) -> LoopDecision:
    """Derive the next role transition from durable repository state.

    This function does not start an AI session itself. It provides a deterministic
    decision that the Codex App Director or a scheduled automation can execute.
    The conversation is never the state machine.
    """

    plan_ids = list_plan_ids(paths)
    if not plan_ids:
        return _decision(
            "start_planner",
            "No durable ResearchPlan exists. Preserve the original mission and start an isolated Planner session.",
        )

    plan_id = plan_ids[-1]
    plan_state_path = paths.research / "plans" / plan_id / "STATE.json"
    plan = read_json(plan_state_path, default={})
    if not isinstance(plan, dict) or not plan:
        return _decision(
            "repair_state",
            f"ResearchPlan {plan_id} has no readable STATE.json.",
            plan_id=plan_id,
        )

    plan_status = str(plan.get("status", "unknown"))
    campaign_id = plan.get("selected_campaign")

    if plan_status == "complete":
        return _decision(
            "mission_complete",
            "The latest ResearchPlan is marked complete.",
            plan_id=plan_id,
            plan_status=plan_status,
        )

    if not isinstance(campaign_id, str) or not campaign_id:
        return _decision(
            "run_planner",
            "The Planner has not selected a Campaign yet.",
            plan_id=plan_id,
            plan_status=plan_status,
        )

    campaign_dir = paths.campaigns / campaign_id
    campaign_state = read_json(campaign_dir / "STATE.json", default={})
    contract = read_json(campaign_dir / "CONTRACT.json", default={})
    if (
        not isinstance(campaign_state, dict)
        or not campaign_state
        or not isinstance(contract, dict)
        or not contract
    ):
        return _decision(
            "repair_state",
            f"Selected Campaign {campaign_id} is missing durable Contract or State.",
            plan_id=plan_id,
            campaign_id=campaign_id,
            plan_status=plan_status,
        )

    campaign_status = str(campaign_state.get("status", "unknown"))
    contract_status = str(contract.get("contract_status", "draft"))

    if campaign_status == "draft" or contract_status != "ready":
        return _decision(
            "run_planner",
            f"Campaign {campaign_id} is still a draft; Planner must finish and validate the Contract.",
            plan_id=plan_id,
            campaign_id=campaign_id,
            plan_status=plan_status,
            campaign_status=campaign_status,
        )

    if campaign_status == "ready":
        context_pack = campaign_dir / "CONTEXT_PACK.md"
        goal_prompt = campaign_dir / "GOAL_PROMPT.md"
        if not context_pack.exists() or not goal_prompt.exists():
            return _decision(
                "run_planner",
                f"Campaign {campaign_id} is ready but its bounded Executor pack is incomplete.",
                plan_id=plan_id,
                campaign_id=campaign_id,
                plan_status=plan_status,
                campaign_status=campaign_status,
            )
        return _decision(
            "start_executor",
            f"Start one fresh GPT-5.6 Sol High Goal Mode session for {campaign_id}.",
            plan_id=plan_id,
            campaign_id=campaign_id,
            plan_status=plan_status,
            campaign_status=campaign_status,
        )

    if campaign_status in {"executing", "running", "waiting", "validating", "reporting"}:
        return _decision(
            "monitor_executor",
            f"Campaign {campaign_id} is active. Observe durable checkpoints without injecting unrelated context.",
            plan_id=plan_id,
            campaign_id=campaign_id,
            plan_status=plan_status,
            campaign_status=campaign_status,
        )

    if campaign_status in {"completed", "stopped"}:
        handoff = campaign_dir / "HANDOFF.json"
        if campaign_status == "completed" and not handoff.exists():
            return _decision(
                "repair_state",
                f"Campaign {campaign_id} is completed but has no validated Handoff.",
                plan_id=plan_id,
                campaign_id=campaign_id,
                plan_status=plan_status,
                campaign_status=campaign_status,
            )
        return _decision(
            "resume_planner",
            f"Campaign {campaign_id} finished; resume a Planner epoch from Handoff and durable strategy files.",
            plan_id=plan_id,
            campaign_id=campaign_id,
            plan_status=plan_status,
            campaign_status=campaign_status,
        )

    return _decision(
        "repair_state",
        f"Campaign {campaign_id} has unsupported status {campaign_status!r}.",
        plan_id=plan_id,
        campaign_id=campaign_id,
        plan_status=plan_status,
        campaign_status=campaign_status,
    )


def render_loop_instruction(decision: LoopDecision) -> str:
    details = decision.to_dict()
    common = f"""# Research loop next action

- Action: **{details["action"]}**
- Reason: {details["reason"]}
- ResearchPlan: `{details.get("plan_id") or "none"}`
- Campaign: `{details.get("campaign_id") or "none"}`
- Generated: `{details["generated_at"]}`

The repository and GitHub control plane are the state of record. Do not infer a
transition from remembered conversation alone.
"""
    action = decision.action
    if action in {"start_planner", "run_planner", "resume_planner"}:
        return (
            common
            + """
## Director action

Open or resume an isolated Research Planner session, load the `research-planner`
Skill, and build a fresh bounded Planner Context Pack. For `resume_planner`, use
Campaign Handoff and strategy memory—not the Executor transcript. The Planner
must update the plan and issue at most one next bounded Campaign unless a
parallel portfolio is explicitly budgeted.
"""
        )
    if action == "start_executor":
        return (
            common
            + f"""
## Director action

Open a **fresh** Codex session for `{decision.campaign_id}`, select GPT-5.6 Sol
High, load the `research-executor` Skill, read
`research/campaigns/{decision.campaign_id}/GOAL_PROMPT.md`, and invoke `/goal`.
Never reuse an Executor session from another Campaign.
"""
        )
    if action == "monitor_executor":
        return (
            common
            + """
## Director action

Read the Campaign `STATE.json`, compute job ledger, GitHub Project item, and
latest checkpoint. Report time/GPU/evidence changes to the human. Do not interrupt
the active Goal unless a hard external boundary or invalid evaluation is present.
"""
        )
    if action == "mission_complete":
        return (
            common
            + "\n## Director action\n\nGenerate the final evidence summary and mark the GitHub Project complete.\n"
        )
    return (
        common
        + "\n## Director action\n\nRepair the durable state before starting another research session.\n"
    )


def write_loop_state(paths: LabPaths) -> dict[str, Any]:
    decision = inspect_research_loop(paths)
    value = decision.to_dict()
    paths.ensure_runtime()
    atomic_write_json(paths.local / "loop.json", value)
    atomic_write_text(paths.runtime / "next-research-action.md", render_loop_instruction(decision))
    return value
