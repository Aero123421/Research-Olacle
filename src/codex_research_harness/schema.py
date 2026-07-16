from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

CAMPAIGN_ID_RE = re.compile(r"^C-\d{3,}$")
EXPERIMENT_ID_RE = re.compile(r"^EXP-[A-Za-z0-9._-]+$")
DRAFT_MARKERS = ("planner must", "replace this", "must define")


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class ValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues = list(issues)
        super().__init__("; ".join(str(issue) for issue in self.issues))


def _require_mapping(value: Any, path: str, issues: list[ValidationIssue]) -> bool:
    if not isinstance(value, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return False
    return True


def _require_nonempty_string(
    mapping: dict[str, Any], key: str, issues: list[ValidationIssue], path: str = "$"
) -> None:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(f"{path}.{key}", "must be a non-empty string"))


def _require_string_list(
    mapping: dict[str, Any],
    key: str,
    issues: list[ValidationIssue],
    *,
    minimum: int = 1,
    path: str = "$",
) -> None:
    value = mapping.get(key)
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        issues.append(
            ValidationIssue(
                f"{path}.{key}",
                f"must be a list of at least {minimum} non-empty string(s)",
            )
        )


def _contains_draft_marker(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.casefold()
        return any(marker in lowered for marker in DRAFT_MARKERS)
    if isinstance(value, list):
        return any(_contains_draft_marker(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_draft_marker(item) for item in value.values())
    return False


def _validate_ready_content(value: dict[str, Any], issues: list[ValidationIssue]) -> None:
    for key in (
        "why_now",
        "decision_to_unlock",
        "scope",
        "success_conditions",
        "withdrawal_conditions",
        "counter_hypotheses",
        "metric_gaming_risks",
        "reversal_evidence",
        "adoption_exclusions",
        "evidence_inputs",
    ):
        if _contains_draft_marker(value.get(key)):
            issues.append(
                ValidationIssue(
                    f"$.{key}",
                    "contains unresolved Planner draft text and cannot be marked ready",
                )
            )


def validate_campaign_contract(value: Any, *, require_ready: bool = True) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not _require_mapping(value, "$", issues):
        return issues
    assert isinstance(value, dict)

    version = value.get("schema_version")
    if isinstance(version, bool) or version not in {1, 2}:
        issues.append(ValidationIssue("$.schema_version", "must be 1 or 2"))
    is_v2 = version == 2

    for key in ("campaign_id", "title", "mission", "goal", "why_now", "decision_to_unlock"):
        _require_nonempty_string(value, key, issues)
    if isinstance(value.get("campaign_id"), str) and not CAMPAIGN_ID_RE.match(value["campaign_id"]):
        issues.append(ValidationIssue("$.campaign_id", "must look like C-001"))

    status = value.get("contract_status")
    if status not in {"draft", "ready"}:
        issues.append(ValidationIssue("$.contract_status", "must be draft or ready"))
    elif require_ready and status != "ready":
        issues.append(ValidationIssue("$.contract_status", "must be ready before Goal Mode activation"))
    elif status == "ready":
        _validate_ready_content(value, issues)

    scope = value.get("scope")
    if _require_mapping(scope, "$.scope", issues):
        assert isinstance(scope, dict)
        _require_string_list(scope, "in", issues, path="$.scope")
        _require_string_list(scope, "out", issues, path="$.scope")

    for key in (
        "success_conditions",
        "withdrawal_conditions",
        "fixed_constraints",
        "forbidden_detours",
        "evidence_inputs",
        "required_outputs",
    ):
        _require_string_list(value, key, issues)

    epistemic_fields = (
        "counter_hypotheses",
        "metric_gaming_risks",
        "reversal_evidence",
        "adoption_exclusions",
    )
    for key in epistemic_fields:
        if is_v2 or key in value:
            _require_string_list(value, key, issues)

    budget = value.get("budget")
    if _require_mapping(budget, "$.budget", issues):
        assert isinstance(budget, dict)
        for key in ("wall_hours", "gpu_hours", "paid_compute_jpy"):
            raw = budget.get(key)
            minimum = 0 if key != "wall_hours" else 0.000001
            if isinstance(raw, bool) or not isinstance(raw, int | float) or raw < minimum:
                qualifier = "positive" if key == "wall_hours" else "non-negative"
                issues.append(ValidationIssue(f"$.budget.{key}", f"must be a {qualifier} number"))

    policy = value.get("checkpoint_policy")
    if _require_mapping(policy, "$.checkpoint_policy", issues):
        assert isinstance(policy, dict)
        fractions = policy.get("budget_fractions")
        if (
            not isinstance(fractions, list)
            or not fractions
            or not all(
                not isinstance(item, bool) and isinstance(item, int | float) and 0 < item < 1
                for item in fractions
            )
        ):
            issues.append(
                ValidationIssue(
                    "$.checkpoint_policy.budget_fractions",
                    "must be a non-empty list of numbers between 0 and 1",
                )
            )
        elif list(fractions) != sorted(set(fractions)):
            issues.append(
                ValidationIssue(
                    "$.checkpoint_policy.budget_fractions",
                    "must be unique and strictly increasing",
                )
            )
        _require_string_list(policy, "events", issues, path="$.checkpoint_policy")

    amendment = value.get("amendment_policy")
    if is_v2 or "amendment_policy" in value:
        if _require_mapping(amendment, "$.amendment_policy", issues):
            assert isinstance(amendment, dict)
            _require_string_list(
                amendment,
                "requires_replanning_for",
                issues,
                path="$.amendment_policy",
            )
            _require_nonempty_string(
                amendment,
                "record_location",
                issues,
                path="$.amendment_policy",
            )

    _require_nonempty_string(value, "evaluation_contract", issues)
    owner = value.get("owner")
    if _require_mapping(owner, "$.owner", issues):
        assert isinstance(owner, dict)
        profile = owner.get("runtime_profile")
        legacy_fields = ("runtime", "model", "effort")
        has_legacy = all(isinstance(owner.get(key), str) and owner[key].strip() for key in legacy_fields)
        if not (isinstance(profile, str) and profile.strip()) and not has_legacy:
            issues.append(
                ValidationIssue(
                    "$.owner",
                    "must define runtime_profile or the legacy runtime/model/effort fields",
                )
            )

    return issues


def validate_campaign_handoff(value: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not _require_mapping(value, "$", issues):
        return issues
    assert isinstance(value, dict)
    version = value.get("schema_version", 1)
    if isinstance(version, bool) or version not in {1, 2}:
        issues.append(ValidationIssue("$.schema_version", "must be 1 or 2 when present"))
    is_v2 = version == 2

    for key in ("campaign_id", "outcome", "summary"):
        _require_nonempty_string(value, key, issues)
    if isinstance(value.get("campaign_id"), str) and not CAMPAIGN_ID_RE.match(value["campaign_id"]):
        issues.append(ValidationIssue("$.campaign_id", "must look like C-001"))

    allowed = {
        "success",
        "promising",
        "rejected_with_evidence",
        "surprise",
        "strategy_conflict",
        "blocked",
        "budget_exhausted",
        "invalid",
    }
    if value.get("outcome") not in allowed:
        issues.append(ValidationIssue("$.outcome", f"must be one of {sorted(allowed)}"))

    for key in (
        "confirmed_findings",
        "rejected_hypotheses",
        "unexpected_observations",
        "strategic_implications",
        "executor_recommendations",
        "limitations",
    ):
        raw = value.get(key)
        if not isinstance(raw, list) or not all(isinstance(item, str) and item.strip() for item in raw):
            issues.append(ValidationIssue(f"$.{key}", "must be a list of non-empty strings"))

    epistemic_residue = (
        "assumptions",
        "unresolved_questions",
        "unverified_leads",
        "decision_reversal_evidence",
    )
    for key in epistemic_residue:
        if is_v2 or key in value:
            raw = value.get(key)
            if not isinstance(raw, list) or not all(isinstance(item, str) and item.strip() for item in raw):
                issues.append(ValidationIssue(f"$.{key}", "must be a list of non-empty strings"))

    evidence = value.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        issues.append(ValidationIssue("$.evidence", "must be a non-empty list"))
    elif isinstance(evidence, list):
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                issues.append(ValidationIssue(f"$.evidence[{index}]", "must be an object"))
                continue
            for key in ("claim", "artifact", "commit"):
                _require_nonempty_string(item, key, issues, path=f"$.evidence[{index}]")
            if is_v2:
                for key in ("observation", "inference"):
                    _require_nonempty_string(item, key, issues, path=f"$.evidence[{index}]")
            else:
                if "observation" in item:
                    _require_nonempty_string(
                        item,
                        "observation",
                        issues,
                        path=f"$.evidence[{index}]",
                    )
                if "inference" in item:
                    _require_nonempty_string(
                        item,
                        "inference",
                        issues,
                        path=f"$.evidence[{index}]",
                    )

            if is_v2 or "confidence" in item:
                if item.get("confidence") not in {"low", "medium", "high"}:
                    issues.append(
                        ValidationIssue(
                            f"$.evidence[{index}].confidence",
                            "must be low, medium, or high",
                        )
                    )

    resources = value.get("resources_actual")
    if _require_mapping(resources, "$.resources_actual", issues):
        assert isinstance(resources, dict)
        for key in ("wall_hours", "gpu_hours", "cost_jpy"):
            raw = resources.get(key)
            if isinstance(raw, bool) or not isinstance(raw, int | float) or raw < 0:
                issues.append(ValidationIssue(f"$.resources_actual.{key}", "must be a non-negative number"))
    return issues


def validate_experiment(value: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not _require_mapping(value, "$", issues):
        return issues
    assert isinstance(value, dict)
    for key in ("experiment_id", "campaign_id", "hypothesis", "status", "git_commit"):
        _require_nonempty_string(value, key, issues)
    if isinstance(value.get("campaign_id"), str) and not CAMPAIGN_ID_RE.match(value["campaign_id"]):
        issues.append(ValidationIssue("$.campaign_id", "must look like C-001"))
    if isinstance(value.get("experiment_id"), str) and not EXPERIMENT_ID_RE.match(value["experiment_id"]):
        issues.append(ValidationIssue("$.experiment_id", "must look like EXP-name"))
    allowed = {"planned", "running", "completed", "failed", "invalid", "cancelled"}
    if value.get("status") not in allowed:
        issues.append(ValidationIssue("$.status", f"must be one of {sorted(allowed)}"))
    metrics = value.get("metrics", {})
    if not isinstance(metrics, dict):
        issues.append(ValidationIssue("$.metrics", "must be an object when provided"))
    artifacts = value.get("artifacts", [])
    if not isinstance(artifacts, list):
        issues.append(ValidationIssue("$.artifacts", "must be a list when provided"))
    elif not all(isinstance(item, str | dict) for item in artifacts):
        issues.append(ValidationIssue("$.artifacts", "items must be paths or artifact objects"))
    resources = value.get("resources", {})
    if not isinstance(resources, dict):
        issues.append(ValidationIssue("$.resources", "must be an object when provided"))
    return issues


def validate_or_raise(value: Any, validator: Callable[[Any], list[ValidationIssue]]) -> None:
    issues = validator(value)
    if issues:
        raise ValidationError(issues)
