from __future__ import annotations

import platform
from typing import Any

from .consultation import configure_browser
from .models import LabPaths
from .utils import atomic_write_json, atomic_write_text, iso_now, read_json

DEFAULT_ANSWERS: dict[str, Any] = {
    "profile": "kaggle",
    "language": "ja",
    "user_level": {
        "github": "beginner",
        "git": "beginner",
        "statistics": "beginner",
        "machine_learning": "beginner",
        "agent_operations": "advanced",
    },
    "communication": {
        "default_depth": "executive",
        "explain_first_use_terms": True,
        "max_new_terms_per_update": 2,
        "prefer_visuals": True,
        "update_policy": "event_driven",
    },
    "browser": {"mode": None, "chrome_profile": None},
    "chatgpt": {
        "preferred_model_labels": ["Pro"],
        "allow_silent_fallback": False,
        "project_only_memory": True,
    },
    "compute": {
        "local_gpu_max_hours_per_day": 20.0,
        "campaign_gpu_hours_default": 8.0,
        "paid_compute_enabled": False,
        "paid_compute_monthly_limit_jpy": 0.0,
        "paid_compute_per_job_limit_jpy": 0.0,
    },
    "autonomy": {
        "research_decisions": "autonomous",
        "campaign_start": "autonomous_after_validation",
        "campaign_stop": "autonomous",
        "replanning": "autonomous",
        "kaggle_submission": "policy_defined",
        "new_paid_provider": "external_action_required",
        "credentials": "external_action_required",
        "destructive_actions": "external_action_required",
    },
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def initialize_repository(
    paths: LabPaths,
    *,
    answers: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Create or resume repository-local setup state.

    Initialization is intentionally idempotent. A first run without interview
    answers creates the durable setup envelope but leaves browser and resource
    choices unselected. Later calls merge new answers and advance the same
    instance instead of creating parallel setup state.
    """

    paths.ensure_runtime()
    state_path = paths.local / "instance.json"
    answers_path = paths.local / "answers.json"
    existing = {} if force else read_json(state_path, default={})
    previous_answers = {} if force else read_json(answers_path, default={})

    if existing and existing.get("initialized") and answers is None and not force:
        return existing

    values = _merge(DEFAULT_ANSWERS, previous_answers if isinstance(previous_answers, dict) else {})
    values = _merge(values, answers or {})
    browser = values.get("browser", {})
    browser_mode = browser.get("mode") if isinstance(browser, dict) else None
    if browser_mode:
        configure_browser(paths, mode=browser_mode, chrome_profile=browser.get("chrome_profile"))

    now = iso_now()
    instance = {
        "schema_version": 1,
        "initialized": True,
        "template_version": "0.1.0",
        "root": str(paths.root),
        "host_platform": platform.platform(),
        "profile": values["profile"],
        "language": values["language"],
        "stage": "environment_discovery" if browser_mode else "setup_interview",
        "browser_mode": browser_mode or "unselected",
        "created_at": existing.get("created_at", now) if isinstance(existing, dict) else now,
        "updated_at": now,
    }
    atomic_write_json(state_path, instance)
    atomic_write_json(answers_path, values)
    _write_human_profile(paths, values)
    _write_compute_policy(paths, values)
    _write_autonomy_policy(paths, values)
    _write_agent_roster(paths, values)
    _write_setup_report(paths, values, instance)
    return instance


def _write_human_profile(paths: LabPaths, values: dict[str, Any]) -> None:
    level = values["user_level"]
    comm = values["communication"]
    atomic_write_json(
        paths.research / "human" / "PROFILE.json",
        {
            "schema_version": 1,
            "human_role": "observer_owner",
            "research_decisions_required": False,
            "language": values["language"],
            "knowledge": level,
            "communication": comm,
            "updated_at": iso_now(),
        },
    )
    atomic_write_text(
        paths.setup / "HUMAN_PROFILE.md",
        f"""# Human communication profile

The human is the **observer-owner**, not the scientific approval gate.
Research must not pause for routine scientific judgment.

## Explanation level

- GitHub: `{level["github"]}`
- Git: `{level["git"]}`
- Statistics: `{level["statistics"]}`
- Machine learning: `{level["machine_learning"]}`
- Agent operations: `{level["agent_operations"]}`

## Communication defaults

- Default depth: `{comm["default_depth"]}`
- Explain terms on first use: `{comm["explain_first_use_terms"]}`
- Maximum new technical terms per normal update: `{comm["max_new_terms_per_update"]}`
- Prefer diagrams/charts: `{comm["prefer_visuals"]}`
- Update policy: `{comm["update_policy"]}`

A normal status update must answer: what is running, whether evidence is
improving the strategy, time/GPU used, what happens next, and whether the
research harness itself is healthy.
""",
    )


def _write_compute_policy(paths: LabPaths, values: dict[str, Any]) -> None:
    c = values["compute"]
    atomic_write_text(
        paths.setup / "COMPUTE_POLICY.md",
        f"""# Compute policy

- Primary backend: local Windows host
- Local GPU maximum per day: **{c["local_gpu_max_hours_per_day"]} hours**
- Default campaign GPU budget: **{c["campaign_gpu_hours_default"]} hours**
- Paid compute enabled: **{c["paid_compute_enabled"]}**
- Monthly paid-compute hard limit: **JPY {c["paid_compute_monthly_limit_jpy"]}**
- Per-job paid-compute hard limit: **JPY {c["paid_compute_per_job_limit_jpy"]}**

Kaggle notebooks, Colab, and SSH rental GPUs are optional backends discovered
at init. Colab must not be placed on the critical path unless its runtime and
persistence constraints are explicitly accepted. Paid jobs require automatic
shutdown and measured cost accounting.
""",
    )


def _write_autonomy_policy(paths: LabPaths, values: dict[str, Any]) -> None:
    a = values["autonomy"]
    atomic_write_text(
        paths.setup / "AUTONOMY_POLICY.md",
        f"""# Autonomy policy

The AI system owns scientific planning, hypothesis selection, experiment
selection, continuation, withdrawal, and replanning.

- Research decisions: `{a["research_decisions"]}`
- Campaign start: `{a["campaign_start"]}`
- Campaign stop: `{a["campaign_stop"]}`
- Replanning: `{a["replanning"]}`
- Kaggle submission: `{a["kaggle_submission"]}`
- New paid provider: `{a["new_paid_provider"]}`
- Credentials/login: `{a["credentials"]}`
- Destructive external actions: `{a["destructive_actions"]}`

Missing optional advisors must degrade gracefully. Only external boundaries
that an AI cannot lawfully or technically cross—login, terms acceptance,
credentials, or hard resource limits—may pause the affected capability.
""",
    )


def _write_agent_roster(paths: LabPaths, values: dict[str, Any]) -> None:
    preferred = values["chatgpt"]["preferred_model_labels"]
    atomic_write_text(
        paths.setup / "AGENT_ROSTER.md",
        f"""# Agent roster

Actual model IDs and effort controls are discovered at init and recorded in
local state. Roles are stable even when models change.

| Role | Default runtime | Responsibility |
|---|---|---|
| Research Director | Codex App | Human conversation, control-plane observation, loop supervision |
| Research Planner | Codex, isolated planner session | EDA, domain research, broad strategy, Campaign Contract |
| Research Executor | GPT-5.6 Sol High, `/goal` | One campaign, deep autonomous experimentation |
| General senior research partner | ChatGPT Project | Broad high-level consultation without a narrow role |
| Methodology auditor | Claude Code | Independent CV/leakage/methodology criticism |
| Realtime/divergent scout | Grok Build | X/community search and alternative hypotheses |

ChatGPT preferred model labels, in order: `{preferred}`. The browser skill must
verify the exact selected label and must never silently fall back.
""",
    )


def _write_setup_report(paths: LabPaths, values: dict[str, Any], instance: dict[str, Any]) -> None:
    atomic_write_text(
        paths.setup / "SETUP_REPORT.md",
        f"""# Setup report

Initialization state was created at `{instance["created_at"]}`.

- Profile: `{values["profile"]}`
- Human language: `{values["language"]}`
- Browser choice: `{values["browser"].get("mode") or "not selected yet"}`
- Scientific decisions: autonomous
- Current stage: environment discovery

Next steps:

1. Run `researchctl doctor --profile full`.
2. Use `github-project-setup` to build the control plane.
3. Use `chatgpt-research-partner` to create and verify the dedicated ChatGPT Project.
4. Preserve the user's vague goal in `research/USER_INTENT.md`.
5. Start the Research Planner; do not launch expensive Goal Mode work until a valid Campaign Contract exists.
""",
    )
