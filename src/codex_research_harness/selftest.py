from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import LabPaths
from .utils import read_toml, safe_relpath

FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def run_self_test(paths: LabPaths) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        "AGENTS.md",
        "BOOTSTRAP.md",
        "TEMPLATE_VERSION",
        ".codex/config.toml",
        ".research-lab/template-manifest.json",
        ".research-lab/init-answers.example.json",
        ".research-lab/project-spec.json",
        ".research-lab/schema/campaign-contract.schema.json",
        ".research-lab/schema/campaign-handoff.schema.json",
        ".research-lab/schema/epistemic-claim-event.schema.json",
        ".research-lab/schema/experiment.schema.json",
        "research/protocols/PLANNER_PROTOCOL.md",
        "research/protocols/EXECUTOR_PROTOCOL.md",
        "research/protocols/CONTEXT_BOUNDARIES.md",
        "research/strategy/CLAIMS.jsonl",
        "research/strategy/CLAIMS.md",
        "docs/INITIAL_INTERVIEW.md",
        "docs/UPSTREAM_REFERENCES.md",
        ".editorconfig",
        ".gitattributes",
        "docs/RELEASE_CHECKLIST.md",
        "scripts/bootstrap.ps1",
        "scripts/researchctl.ps1",
        "scripts/verify.ps1",
        ".agents/skills/research-bootstrap/SKILL.md",
        ".agents/skills/research-planner/SKILL.md",
        ".agents/skills/research-executor/SKILL.md",
        ".agents/skills/research-loop/SKILL.md",
        ".agents/skills/chatgpt-research-partner/SKILL.md",
        ".claude/agents/methodology-auditor.md",
        ".claude/skills/methodology-audit/SKILL.md",
        ".grok/skills/x-research-scout/SKILL.md",
    ]
    for relative in required:
        if not (paths.root / relative).exists():
            errors.append(f"Missing required file: {relative}")

    codex_config = read_toml(paths.root / ".codex" / "config.toml")
    if not codex_config.get("features", {}).get("goals"):
        errors.append(".codex/config.toml must enable [features] goals = true")

    for relative in [
        ".research-lab/project-spec.json",
        ".research-lab/template-manifest.json",
        ".research-lab/init-answers.example.json",
        ".research-lab/schema/campaign-contract.schema.json",
        ".research-lab/schema/campaign-handoff.schema.json",
        ".research-lab/schema/epistemic-claim-event.schema.json",
        ".research-lab/schema/experiment.schema.json",
    ]:
        path = paths.root / relative
        if not path.exists():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid JSON in {relative}: {exc}")

    version_path = paths.root / "TEMPLATE_VERSION"
    manifest_path = paths.lab / "template-manifest.json"
    if version_path.exists() and manifest_path.exists():
        version = version_path.read_text(encoding="utf-8").strip()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not version:
            errors.append("TEMPLATE_VERSION must not be blank")
        if manifest.get("name") != "codex-research-harness":
            errors.append("Template manifest name must be 'codex-research-harness'")

    spec_path = paths.lab / "project-spec.json"
    if spec_path.exists():
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        field_names = [item.get("name") for item in spec.get("fields", [])]
        view_names = [item.get("name") for item in spec.get("views", [])]
        if len(field_names) != len(set(field_names)):
            errors.append("GitHub Project field names must be unique")
        if len(view_names) != len(set(view_names)):
            errors.append("GitHub Project view names must be unique")

    skills: dict[str, str] = {}
    for path in sorted(paths.root.glob(".agents/skills/*/SKILL.md")):
        metadata = _frontmatter(path)
        relative = safe_relpath(path, paths.root)
        name = metadata.get("name")
        description = metadata.get("description")
        if not name or not description:
            errors.append(f"Skill {relative} must declare name and description")
            continue
        if name in skills:
            errors.append(f"Duplicate Skill name {name!r}: {skills[name]} and {relative}")
        skills[name] = relative
        if path.parent.name != name:
            warnings.append(f"Skill folder {path.parent.name!r} differs from declared name {name!r}")

    expected_skills = {
        "research-bootstrap",
        "research-planner",
        "research-executor",
        "research-loop",
        "context-checkpoint",
        "campaign-handoff",
        "lab-status",
        "chatgpt-research-partner",
        "github-project-setup",
        "kaggle-recon",
        "eda-diagnostics",
        "expert-consultation",
        "visualize-research",
    }
    missing_skills = sorted(expected_skills - set(skills))
    if missing_skills:
        errors.append("Missing core Skills: " + ", ".join(missing_skills))

    forbidden_terms = {"notebook" + "lm": "Removed human-comprehension integration must not reappear"}
    for path in paths.root.rglob("*"):
        if not path.is_file() or any(
            part in {".git", ".venv", "runtime", "__pycache__"} for part in path.parts
        ):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix.lower() not in {".md", ".py", ".toml", ".json", ".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").casefold()
        for term, reason in forbidden_terms.items():
            if term in text:
                errors.append(
                    f"Forbidden stale architecture term {term!r} in {safe_relpath(path, paths.root)}: {reason}"
                )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "skill_count": len(skills),
        "required_file_count": len(required),
    }
