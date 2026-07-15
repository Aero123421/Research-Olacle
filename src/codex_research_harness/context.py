from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .config import load_context_config
from .models import LabPaths
from .schema import validate_campaign_contract, validate_or_raise
from .utils import atomic_write_text, iso_now, read_json, safe_relpath, truncate_text, word_count


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
    included: list[str]
    missing: list[str]
    total_chars: int
    total_words: int


def _read_source(source: ContextSource, root: Path) -> tuple[str | None, str]:
    relative = safe_relpath(source.path, root)
    if not source.path.exists():
        return None, relative
    text = source.path.read_text(encoding="utf-8", errors="replace")
    return truncate_text(text, max_chars=source.max_chars), relative


def build_pack(
    paths: LabPaths,
    *,
    title: str,
    role: str,
    sources: Iterable[ContextSource],
    output: Path,
    max_chars: int,
    strict_required: bool = True,
) -> ContextPackResult:
    sections = [
        f"# {title}",
        "",
        f"Generated: `{iso_now()}`",
        f"Role: `{role}`",
        "",
        "> This is a bounded context pack. Follow references only when the current",
        "> decision requires them; do not ingest the entire archive by default.",
        "",
    ]
    included: list[str] = []
    missing: list[str] = []
    missing_required: list[str] = []
    current_chars = sum(len(part) for part in sections)
    for source in sources:
        text, relative = _read_source(source, paths.root)
        if text is None:
            missing.append(relative)
            if source.required:
                missing_required.append(relative)
                sections.extend([f"## {source.title}", "", f"**MISSING REQUIRED SOURCE:** `{relative}`", ""])
            continue
        block = f"## {source.title}\n\nSource: `{relative}`\n\n{text.strip()}\n"
        if current_chars + len(block) > max_chars:
            remaining = max(0, max_chars - current_chars - 160)
            if remaining > 500:
                block = truncate_text(block, max_chars=remaining)
                sections.append(block)
                included.append(relative)
            sections.extend(
                ["", "## Context budget reached", "", f"Further sources were omitted after `{relative}`.", ""]
            )
            break
        sections.append(block)
        included.append(relative)
        current_chars += len(block)
    text = "\n".join(sections).rstrip() + "\n"
    atomic_write_text(output, text)
    result = ContextPackResult(output, included, missing, len(text), word_count(text))
    if strict_required and missing_required:
        raise ContextPackError(
            "Cannot build a runnable context pack; required sources are missing: "
            + ", ".join(missing_required)
        )
    return result


def build_planner_context(paths: LabPaths, *, output: Path | None = None) -> ContextPackResult:
    config = load_context_config(paths)
    max_chars = int(config.get("budgets", {}).get("planner_max_chars", 100_000))
    sources = [
        ContextSource("Original human intent", paths.research / "USER_INTENT.md", True, 12_000),
        ContextSource("Mission", paths.research / "MISSION.md", True, 12_000),
        ContextSource("Current strategy", paths.strategy / "CURRENT.md", True, 18_000),
        ContextSource("Strategy memory", paths.strategy / "MEMORY.md", True, 22_000),
        ContextSource("Research landscape", paths.strategy / "LANDSCAPE.md", False, 18_000),
        ContextSource("Domain map", paths.strategy / "DOMAIN_MAP.md", False, 16_000),
        ContextSource("Cross-domain analogies", paths.strategy / "ANALOGIES.md", False, 16_000),
        ContextSource("Strategy portfolio", paths.strategy / "PORTFOLIO.md", False, 14_000),
        ContextSource("Open questions", paths.strategy / "OPEN_QUESTIONS.md", False, 12_000),
        ContextSource("Evidence index", paths.strategy / "EVIDENCE_INDEX.md", False, 18_000),
        ContextSource("Compute policy", paths.setup / "COMPUTE_POLICY.md", True, 8_000),
    ]
    plan_directories = sorted(
        (path for path in (paths.research / "plans").glob("RP-*") if path.is_dir()),
        key=lambda path: path.name,
    )
    if plan_directories:
        latest_plan = plan_directories[-1]
        sources.extend(
            [
                ContextSource("Current ResearchPlan", latest_plan / "PLAN.md", True, 24_000),
                ContextSource("ResearchPlan state", latest_plan / "STATE.json", True, 8_000),
                ContextSource(
                    "ResearchPlan evidence index", latest_plan / "evidence" / "README.md", False, 12_000
                ),
            ]
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
    for consultation_dir in consultation_dirs[-max(0, consultation_retention) :]:
        sources.append(
            ContextSource(
                f"Advisor synthesis {consultation_dir.name}",
                consultation_dir / "SYNTHESIS.md",
                False,
                8_000,
            )
        )

    retention = int(config.get("retention", {}).get("planner_campaign_reports", 8))
    campaign_ids = sorted(path.name for path in paths.campaigns.glob("C-*") if path.is_dir())
    for campaign_id in campaign_ids[-max(0, retention) :]:
        sources.append(
            ContextSource(
                f"Campaign handoff {campaign_id}",
                paths.campaigns / campaign_id / "HANDOFF.md",
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
    )


def build_executor_context(
    paths: LabPaths, campaign_id: str, *, output: Path | None = None
) -> ContextPackResult:
    config = load_context_config(paths)
    max_chars = int(config.get("budgets", {}).get("executor_max_chars", 80_000))
    directory = paths.campaigns / campaign_id
    contract = read_json(directory / "CONTRACT.json", default={})
    if not contract:
        raise FileNotFoundError(f"Unknown campaign {campaign_id}")
    validate_or_raise(contract, lambda value: validate_campaign_contract(value, require_ready=True))
    evidence_sources = []
    for raw in contract.get("evidence_inputs", []):
        if isinstance(raw, str):
            evidence_sources.append(ContextSource(f"Evidence: {raw}", paths.root / raw, True, 16_000))
    evaluation_path = paths.root / str(contract.get("evaluation_contract", ""))
    sources = [
        ContextSource("Campaign contract", directory / "CONTRACT.json", True, 24_000),
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
