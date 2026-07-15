from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from codex_research_harness.campaign import default_contract
from codex_research_harness.models import LabPaths
from codex_research_harness.utils import atomic_write_json


def make_repo(tmp_path: Path) -> LabPaths:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    source_root = Path(__file__).resolve().parents[1]
    for relative in [
        ".research-lab/config",
        ".research-lab/schema",
        "research/setup",
        "research/strategy",
        "research/protocols",
        "research/campaigns",
        "research/consultations",
        "research/human",
        "experiments",
        "reports/visuals",
        "reports/cockpit",
        "runtime",
        ".agents/skills/research-planner",
        ".agents/skills/research-executor",
        ".agents/skills/chatgpt-research-partner",
    ]:
        (root / relative).mkdir(parents=True, exist_ok=True)
    for relative in [
        ".research-lab/config/lab.toml",
        ".research-lab/config/agents.toml",
        ".research-lab/config/compute.toml",
        ".research-lab/config/context.toml",
        ".research-lab/project-spec.json",
        ".research-lab/schema/campaign-contract.schema.json",
        ".research-lab/schema/campaign-handoff.schema.json",
        ".research-lab/schema/experiment.schema.json",
        "research/USER_INTENT.md",
        "research/MISSION.md",
        "research/strategy/CURRENT.md",
        "research/strategy/MEMORY.md",
        "research/strategy/LANDSCAPE.md",
        "research/strategy/DOMAIN_MAP.md",
        "research/strategy/ANALOGIES.md",
        "research/strategy/PORTFOLIO.md",
        "research/strategy/OPEN_QUESTIONS.md",
        "research/strategy/EVIDENCE_INDEX.md",
        "research/protocols/EVALUATION_CONTRACT.md",
        "research/setup/COMPUTE_POLICY.md",
        "research/setup/AGENT_ROSTER.md",
        "AGENTS.md",
        "BOOTSTRAP.md",
        ".agents/skills/research-planner/SKILL.md",
        ".agents/skills/research-executor/SKILL.md",
        ".agents/skills/chatgpt-research-partner/SKILL.md",
    ]:
        source = source_root / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    paths = LabPaths(root)
    paths.ensure_runtime()
    return paths


def ready_contract(campaign_id: str = "C-001") -> dict[str, Any]:
    value = default_contract(
        campaign_id, "Explore robust signal", "Determine whether a new signal improves robust validation"
    )
    value.update(
        {
            "contract_status": "ready",
            "why_now": "Current evidence has plateaued and this test distinguishes two strategic explanations.",
            "decision_to_unlock": "Decide whether to allocate the next full-CV block to this signal family.",
            "scope": {
                "in": ["Reproducible quick and full validation of the proposed signal"],
                "out": ["Unrelated model families and general infrastructure"],
            },
            "success_conditions": ["The predefined evaluation improves by at least 0.002 across two seeds."],
            "withdrawal_conditions": [
                "Withdraw after three valid quick tests show no directional improvement."
            ],
            "evidence_inputs": ["research/strategy/EVIDENCE_INDEX.md"],
        }
    )
    return value


def write_ready_contract(paths: LabPaths, campaign_id: str = "C-001") -> dict[str, Any]:
    value = ready_contract(campaign_id)
    atomic_write_json(paths.campaigns / campaign_id / "CONTRACT.json", value)
    return value


def valid_handoff(campaign_id: str = "C-001", artifact: str = "artifacts/evidence.txt") -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "outcome": "rejected_with_evidence",
        "summary": "The hypothesis did not survive confirmation, but the negative result changes the strategy.",
        "evidence": [
            {
                "claim": "No stable improvement across confirmation runs",
                "experiment_id": "EXP-001",
                "artifact": artifact,
                "commit": "0123456789abcdef",
            }
        ],
        "confirmed_findings": ["No stable improvement"],
        "rejected_hypotheses": ["The signal improves every fold"],
        "unexpected_observations": [],
        "strategic_implications": ["Explore a different signal family"],
        "executor_recommendations": ["Revisit validation shift"],
        "resources_actual": {"wall_hours": 2, "gpu_hours": 1, "cost_jpy": 0},
        "limitations": ["Two seeds only"],
    }
