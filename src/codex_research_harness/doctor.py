from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_lab_config
from .models import DoctorReport, LabPaths, ProbeResult
from .probes import build_probes
from .utils import atomic_write_json, atomic_write_text, markdown_table, read_json

STATUS_ICON = {"pass": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭️"}


def doctor_output_paths(paths: LabPaths) -> tuple[Path, Path]:
    """Return commit-safe output paths for the current bootstrap stage.

    Before repository adoption/materialization, Doctor must not dirty the
    template clone. Once setup has been materialized in the adopted research
    repository, the bounded census/readiness reports become reviewable tracked
    state under ``research/setup``.
    """

    instance = read_json(paths.local / "instance.json", default={})
    materialized = isinstance(instance, dict) and bool(instance.get("materialized"))
    base = paths.setup if materialized else paths.local / "setup"
    return base / "AGENT_CENSUS.json", base / "READINESS.md"


def run_doctor(paths: LabPaths, *, profile: str = "full") -> DoctorReport:
    config = load_lab_config(paths)
    results: list[ProbeResult] = []
    for probe in build_probes(paths, config, profile):
        try:
            results.append(probe.run())
        except Exception as exc:  # defensive: one broken probe must not hide the rest
            results.append(
                ProbeResult(
                    name=getattr(probe, "name", probe.__class__.__name__),
                    status="fail",
                    summary=f"Probe raised {type(exc).__name__}: {exc}",
                    category=getattr(probe, "category", "core"),
                    remediation=["Inspect the probe output and rerun with `researchctl doctor --json`."],
                )
            )
    report = DoctorReport(results=results, profile=profile)
    paths.ensure_runtime()
    atomic_write_json(paths.runtime / "doctor.json", report.to_dict())
    census_path, readiness_path = doctor_output_paths(paths)
    atomic_write_json(census_path, render_safe_agent_census(report))
    atomic_write_text(readiness_path, render_doctor_markdown(report))
    return report


def render_safe_agent_census(report: DoctorReport) -> dict[str, Any]:
    """Return a commit-safe capability census without auth text, URLs, or tokens."""

    allowed_detail_keys = {
        "version",
        "version_tuple",
        "authenticated",
        "goals_enabled",
        "doctor_ok",
        "adapter_present",
        "x_skill_present",
        "live_x_search_verified",
        "model_label",
        "browser_mode",
        "last_verified_at",
    }
    agents = []
    for result in report.results:
        if result.category not in {"agents", "advisors", "communication", "chatgpt"}:
            continue
        details = {
            key: value
            for key, value in result.details.items()
            if key in allowed_detail_keys and isinstance(value, str | int | float | bool | list | type(None))
        }
        agents.append(
            {
                "name": result.name,
                "category": result.category,
                "status": result.status,
                "summary": result.summary,
                "details": details,
            }
        )
    return {
        "schema_version": 1,
        "generated_at": report.generated_at,
        "profile": report.profile,
        "agents": agents,
        "note": "Authentication secrets, command output, browser URLs, and profile paths are intentionally omitted.",
    }


def render_doctor_markdown(report: DoctorReport) -> str:
    categories = sorted({result.category for result in report.results})
    rows = []
    for category in categories:
        status = report.category_status(category)
        rows.append((category, f"{STATUS_ICON[status]} {status.upper()}"))
    detail_rows = [
        (
            f"{STATUS_ICON[result.status]} {result.name}",
            result.category,
            result.summary.replace("\n", " "),
        )
        for result in report.results
    ]
    remediation = []
    for result in report.results:
        for item in result.remediation:
            remediation.append(f"- **{result.name}:** {item}")
    counts = report.counts
    overall = "READY" if counts["fail"] == 0 else "NOT READY"
    return f"""# Research Lab Readiness

Generated: `{report.generated_at}`

Profile: `{report.profile}`

Overall: **{overall}**

## Category status

{markdown_table(("Category", "Status"), rows)}

## Checks

{markdown_table(("Check", "Category", "Result"), detail_rows)}

## Required actions

{chr(10).join(remediation) if remediation else "No blocking remediation is required."}

> Optional advisor failures do not block autonomous research. Core repository,
> Codex execution, state persistence, and at least one compute path are the hard
> readiness boundary.
"""


def doctor_exit_code(report: DoctorReport, *, strict: bool = False) -> int:
    if report.counts["fail"]:
        return 2
    if strict and report.counts["warn"]:
        return 1
    return 0
