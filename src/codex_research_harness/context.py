from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import load_context_config
from .models import LabPaths
from .schema import validate_campaign_contract, validate_or_raise
from .utils import (
    atomic_write_json,
    atomic_write_text,
    iso_now,
    read_json,
    safe_relpath,
    truncate_text,
    word_count,
)


class ContextPackError(ValueError):
    pass


@dataclass(frozen=True)
class ContextSource:
    title: str
    path: Path
    required: bool = False
    max_chars: int = 30_000


@dataclass
class ContextPackResult:
    output: Path
    manifest: Path
    included: list[str]
    missing: list[str]
    total_chars: int
    total_words: int
    valid: bool = True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def context_manifest_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.manifest.json")


def _remove_stale_pack(output: Path) -> None:
    for path in (output, context_manifest_path(output)):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def build_pack(
    paths: LabPaths,
    *,
    title: str,
    role: str,
    sources: Iterable[ContextSource],
    output: Path,
    max_chars: int,
    strict_required: bool = True,
    metadata: dict[str, Any] | None = None,
) -> ContextPackResult:
    """Build a bounded pack and an integrity manifest as one logical unit.

    Every required source is validated before any runnable artifact is written.
    The manifest binds the generated pack to exact source hashes and role-specific
    metadata such as the Campaign Contract hash.
    """

    source_values = list(sources)
    prepared: list[dict[str, Any]] = []
    missing: list[str] = []
    missing_required: list[str] = []

    for source in source_values:
        relative = safe_relpath(source.path, paths.root)
        if not source.path.exists():
            missing.append(relative)
            if source.required:
                missing_required.append(relative)
            prepared.append(
                {
                    "source": source,
                    "path": relative,
                    "exists": False,
                    "text": None,
                    "sha256": None,
                    "original_chars": 0,
                    "source_truncated": False,
                }
            )
            continue
        raw = source.path.read_text(encoding="utf-8", errors="replace")
        text = truncate_text(raw, max_chars=source.max_chars)
        prepared.append(
            {
                "source": source,
                "path": relative,
                "exists": True,
                "text": text,
                "sha256": sha256_file(source.path),
                "original_chars": len(raw),
                "source_truncated": len(text) < len(raw),
            }
        )

    if strict_required and missing_required:
        _remove_stale_pack(output)
        raise ContextPackError(
            "Cannot build a runnable context pack; required sources are missing: "
            + ", ".join(missing_required)
        )

    # Required sources are rendered first so optional historical material can
    # never crowd out the contract, current plan, or newest durable state.
    ordered = [item for item in prepared if item["source"].required] + [
        item for item in prepared if not item["source"].required
    ]
    generated_at = iso_now()
    sections = [
        f"# {title}",
        "",
        f"Generated: `{generated_at}`",
        f"Role: `{role}`",
        "",
        "> This is a bounded context pack. Follow references only when the current",
        "> decision requires them; do not ingest the entire archive by default.",
        "",
    ]
    included: list[str] = []
    records: list[dict[str, Any]] = []
    current_chars = sum(len(part) for part in sections)
    budget_reached = False

    for item in ordered:
        source = item["source"]
        relative = item["path"]
        record = {
            "title": source.title,
            "path": relative,
            "required": source.required,
            "exists": item["exists"],
            "sha256": item["sha256"],
            "original_chars": item["original_chars"],
            "source_truncated": item["source_truncated"],
            "included": False,
            "included_chars": 0,
            "pack_truncated": False,
        }
        records.append(record)
        if not item["exists"]:
            continue

        block = f"## {source.title}\n\nSource: `{relative}`\n\n{str(item['text']).strip()}\n"
        if current_chars + len(block) > max_chars:
            remaining = max(0, max_chars - current_chars - 180)
            if source.required:
                _remove_stale_pack(output)
                raise ContextPackError(
                    f"Required source {relative} cannot fit inside the {max_chars}-character context budget"
                )
            if remaining > 500:
                block = truncate_text(block, max_chars=remaining)
                sections.append(block)
                included.append(relative)
                record["included"] = True
                record["included_chars"] = len(block)
                record["pack_truncated"] = True
            budget_reached = True
            break

        sections.append(block)
        included.append(relative)
        record["included"] = True
        record["included_chars"] = len(block)
        current_chars += len(block)

    if budget_reached:
        sections.extend(
            [
                "",
                "## Context budget reached",
                "",
                "Lower-priority optional sources were omitted. Consult the archive only when a current decision requires it.",
                "",
            ]
        )

    text = "\n".join(sections).rstrip() + "\n"
    manifest_path = context_manifest_path(output)
    manifest = {
        "schema_version": 1,
        "valid": True,
        "role": role,
        "title": title,
        "generated_at": generated_at,
        "output": safe_relpath(output, paths.root),
        "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "total_chars": len(text),
        "total_words": word_count(text),
        "max_chars": max_chars,
        "budget_reached": budget_reached,
        "metadata": metadata or {},
        "sources": records,
    }
    _remove_stale_pack(output)
    try:
        atomic_write_text(output, text)
        atomic_write_json(manifest_path, manifest)
    except Exception:
        _remove_stale_pack(output)
        raise
    return ContextPackResult(
        output=output,
        manifest=manifest_path,
        included=included,
        missing=missing,
        total_chars=len(text),
        total_words=word_count(text),
    )


def validate_context_pack(
    paths: LabPaths,
    output: Path,
    *,
    expected_role: str | None = None,
    expected_metadata: dict[str, Any] | None = None,
) -> list[str]:
    issues: list[str] = []
    manifest_path = context_manifest_path(output)
    manifest = read_json(manifest_path, default={})
    if not output.exists():
        issues.append(f"missing context pack: {safe_relpath(output, paths.root)}")
        return issues
    if not isinstance(manifest, dict) or not manifest:
        issues.append(f"missing or unreadable manifest: {safe_relpath(manifest_path, paths.root)}")
        return issues
    if manifest.get("valid") is not True:
        issues.append("context manifest is not marked valid")
    if expected_role and manifest.get("role") != expected_role:
        issues.append(f"context role mismatch: expected {expected_role!r}, got {manifest.get('role')!r}")
    if manifest.get("output_sha256") != sha256_file(output):
        issues.append("context pack hash does not match its manifest")

    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        issues.append("context manifest metadata is malformed")
        metadata = {}
    for key, expected in (expected_metadata or {}).items():
        if metadata.get(key) != expected:
            issues.append(f"context metadata mismatch for {key}: expected {expected!r}")

    records = manifest.get("sources")
    if not isinstance(records, list):
        issues.append("context manifest source list is malformed")
        return issues
    for record in records:
        if not isinstance(record, dict):
            issues.append("context manifest contains a malformed source record")
            continue
        if not record.get("included"):
            continue
        relative = record.get("path")
        if not isinstance(relative, str) or not relative:
            issues.append("context source record has no path")
            continue
        path = paths.root / relative
        try:
            safe_relpath(path, paths.root)
        except ValueError as exc:
            issues.append(str(exc))
            continue
        if not path.exists():
            issues.append(f"included context source is missing: {relative}")
        elif record.get("sha256") != sha256_file(path):
            issues.append(f"included context source changed after pack generation: {relative}")
    return issues


def build_planner_context(paths: LabPaths, *, output: Path | None = None) -> ContextPackResult:
    config = load_context_config(paths)
    max_chars = int(config.get("budgets", {}).get("planner_max_chars", 100_000))
    sources = [
        ContextSource("Original human intent", paths.research / "USER_INTENT.md", True, 12_000),
        ContextSource("Mission", paths.research / "MISSION.md", True, 12_000),
    ]

    plan_directories = sorted(
        (path for path in (paths.research / "plans").glob("RP-*") if path.is_dir()),
        key=lambda path: path.name,
    )
    metadata: dict[str, Any] = {}
    if plan_directories:
        latest_plan = plan_directories[-1]
        metadata["plan_id"] = latest_plan.name
        sources.extend(
            [
                ContextSource("Current ResearchPlan", latest_plan / "PLAN.md", True, 24_000),
                ContextSource("ResearchPlan state", latest_plan / "STATE.json", True, 8_000),
            ]
        )

    sources.extend(
        [
            ContextSource("Current strategy", paths.strategy / "CURRENT.md", True, 18_000),
            ContextSource("Strategy memory", paths.strategy / "MEMORY.md", True, 22_000),
            ContextSource("Compute policy", paths.setup / "COMPUTE_POLICY.md", True, 8_000),
        ]
    )

    retention = int(config.get("retention", {}).get("planner_campaign_reports", 8))
    campaign_ids = sorted(path.name for path in paths.campaigns.glob("C-*") if path.is_dir())
    for campaign_id in reversed(campaign_ids[-max(0, retention) :]):
        sources.append(
            ContextSource(
                f"Campaign handoff {campaign_id}",
                paths.campaigns / campaign_id / "HANDOFF.md",
                False,
                12_000,
            )
        )

    consultation_retention = int(config.get("retention", {}).get("planner_consultation_summaries", 12))
    consultation_dirs = sorted(
        (
            path
            for path in paths.consultations.glob("Q-*")
            if path.is_dir() and (path / "SYNTHESIS.md").exists()
        ),
        key=lambda path: path.name,
    )
    for consultation_dir in reversed(consultation_dirs[-max(0, consultation_retention) :]):
        sources.append(
            ContextSource(
                f"Advisor synthesis {consultation_dir.name}",
                consultation_dir / "SYNTHESIS.md",
                False,
                8_000,
            )
        )

    sources.extend(
        [
            ContextSource("Open questions", paths.strategy / "OPEN_QUESTIONS.md", False, 12_000),
            ContextSource("Evidence index", paths.strategy / "EVIDENCE_INDEX.md", False, 18_000),
            ContextSource("Strategy portfolio", paths.strategy / "PORTFOLIO.md", False, 14_000),
            ContextSource("Research landscape", paths.strategy / "LANDSCAPE.md", False, 18_000),
            ContextSource("Domain map", paths.strategy / "DOMAIN_MAP.md", False, 16_000),
            ContextSource("Cross-domain analogies", paths.strategy / "ANALOGIES.md", False, 16_000),
        ]
    )
    if plan_directories:
        sources.append(
            ContextSource(
                "ResearchPlan evidence index",
                plan_directories[-1] / "evidence" / "README.md",
                False,
                12_000,
            )
        )

    output = output or paths.runtime / "context" / "planner-context.md"
    return build_pack(
        paths,
        title="Research Planner context",
        role="research-planner",
        sources=sources,
        output=output,
        max_chars=max_chars,
        metadata=metadata,
    )


def build_executor_context(
    paths: LabPaths, campaign_id: str, *, output: Path | None = None
) -> ContextPackResult:
    config = load_context_config(paths)
    max_chars = int(config.get("budgets", {}).get("executor_max_chars", 80_000))
    directory = paths.campaigns / campaign_id
    contract_path = directory / "CONTRACT.json"
    contract = read_json(contract_path, default={})
    if not contract:
        raise FileNotFoundError(f"Unknown campaign {campaign_id}")
    validate_or_raise(contract, lambda value: validate_campaign_contract(value, require_ready=True))
    evidence_sources = []
    for raw in contract.get("evidence_inputs", []):
        if isinstance(raw, str):
            evidence_sources.append(ContextSource(f"Evidence: {raw}", paths.root / raw, True, 16_000))
    evaluation_path = paths.root / str(contract.get("evaluation_contract", ""))
    sources = [
        ContextSource("Campaign contract", contract_path, True, 24_000),
        ContextSource("Current campaign state", directory / "STATE.md", True, 8_000),
        ContextSource("Mission", paths.research / "MISSION.md", True, 10_000),
        ContextSource("Evaluation contract", evaluation_path, True, 14_000),
        ContextSource("Relevant strategy excerpt", paths.strategy / "CURRENT.md", True, 12_000),
        ContextSource("Compute policy", paths.setup / "COMPUTE_POLICY.md", True, 8_000),
        ContextSource("Advisor policy", paths.setup / "AGENT_ROSTER.md", False, 8_000),
        *evidence_sources,
    ]
    output = output or directory / "CONTEXT_PACK.md"
    return build_pack(
        paths,
        title=f"Executor context — {campaign_id}",
        role="research-executor",
        sources=sources,
        output=output,
        max_chars=max_chars,
        metadata={"campaign_id": campaign_id, "contract_sha256": sha256_file(contract_path)},
    )


def check_context_sizes(paths: LabPaths) -> list[str]:
    config = load_context_config(paths)
    limits = config.get("budgets", {})
    checks = [
        (paths.strategy / "MEMORY.md", int(limits.get("strategy_memory_max_chars", 24_000))),
    ]
    for directory in paths.campaigns.glob("C-*"):
        checks.append((directory / "STATE.md", int(limits.get("campaign_state_max_chars", 8_000))))
    warnings = []
    for path, limit in checks:
        if path.exists() and path.stat().st_size > limit:
            warnings.append(
                f"{safe_relpath(path, paths.root)} exceeds {limit} bytes; checkpoint and compact it."
            )
    return warnings
