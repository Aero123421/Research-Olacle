from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from ..utils import read_toml
from .base import Probe


def _version_tuple(text: str) -> tuple[int, ...]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(value) for value in match.groups()) if match else ()


class CodexProbe(Probe):
    name = "codex"
    category = "agents"

    def run(self):
        if not self.command_exists("codex"):
            return self.result(
                "fail",
                "Codex CLI was not found",
                remediation=[
                    "Install or update Codex and sign in from the ChatGPT desktop app or `codex login`."
                ],
            )
        version = self.command(["codex", "--version"])
        auth = self.command(["codex", "login", "status"])
        project_config = read_toml(self.paths.root / ".codex" / "config.toml")
        goals_enabled = bool(project_config.get("features", {}).get("goals"))
        parsed_version = _version_tuple(version.stdout or version.stderr)
        status = "pass" if version.ok and auth.ok and goals_enabled else "warn"
        remediation: list[str] = []
        if not auth.ok:
            remediation.append("Run `codex login` and complete the ChatGPT sign-in flow.")
        if not goals_enabled:
            remediation.append(
                "Set `[features] goals = true` in `.codex/config.toml` or run `codex features enable goals`."
            )
        if parsed_version and parsed_version < (0, 144, 0):
            status = "warn"
            remediation.append(
                "Update Codex; the template is tested against the current Goal Mode generation (0.144+)."
            )
        return self.result(
            status,
            "Codex is authenticated and project Goal Mode is enabled"
            if status == "pass"
            else "Codex needs an update, login, or Goal Mode configuration review",
            details={
                "version": version.stdout or version.stderr,
                "version_tuple": list(parsed_version),
                "authenticated": auth.ok,
                "goals_enabled": goals_enabled,
            },
            remediation=remediation,
        )


class ClaudeProbe(Probe):
    name = "claude-code"
    category = "advisors"

    def run(self):
        if not self.command_exists("claude"):
            return self.result(
                "warn",
                "Claude Code was not found; methodology auditing will use other advisors",
                remediation=["Install Claude Code if you want the independent methodology auditor preset."],
            )
        version = self.command(["claude", "--version"])
        auth = self.command(["claude", "auth", "status", "--text"])
        diagnostics = self.command(["claude", "doctor"], timeout=35)
        adapter = self.paths.root / ".claude" / "agents" / "methodology-auditor.md"
        status = "pass" if version.ok and auth.ok and diagnostics.ok and adapter.exists() else "warn"
        remediation: list[str] = []
        if not auth.ok:
            remediation.append("Run `claude auth login`.")
        if not diagnostics.ok:
            remediation.append("Run `claude doctor` and resolve the reported installation/settings issue.")
        if not adapter.exists():
            remediation.append("Restore `.claude/agents/methodology-auditor.md` from the template.")
        return self.result(
            status,
            "Claude Code and the methodology auditor adapter are ready"
            if status == "pass"
            else "Claude Code needs login, diagnostics, or adapter review",
            details={
                "version": version.stdout or version.stderr,
                "authenticated": auth.ok,
                "doctor_ok": diagnostics.ok,
                "adapter_present": adapter.exists(),
            },
            remediation=remediation,
        )


class GrokProbe(Probe):
    name = "grok-build"
    category = "advisors"

    def run(self):
        if not self.command_exists("grok"):
            return self.result(
                "warn",
                "Grok Build was not found; X/community scouting will be unavailable",
                remediation=["Install Grok Build and run `grok login` if this role is desired."],
            )
        version = self.command(["grok", "version"])
        if not version.ok:
            version = self.command(["grok", "--version"])
        inspect = self.command(["grok", "inspect", "--json"], timeout=30)
        models = self.command(["grok", "models"], timeout=30)
        x_skill = self.paths.root / ".grok" / "skills" / "x-research-scout" / "SKILL.md"
        status = "pass" if inspect.ok and models.ok and x_skill.exists() else "warn"
        inspect_value: Any = inspect.stdout
        if inspect.ok:
            try:
                inspect_value = json.loads(inspect.stdout)
            except json.JSONDecodeError:
                pass
        remediation: list[str] = []
        if not inspect.ok or not models.ok:
            remediation.append("Run `grok login`, then `grok inspect --json` and `grok models`.")
        if not x_skill.exists():
            remediation.append("Restore `.grok/skills/x-research-scout/SKILL.md` from the template.")
        return self.result(
            status,
            "Grok Build and project scouting Skills are discoverable"
            if status == "pass"
            else "Grok Build needs login, model, or Skill discovery review",
            details={
                "version": version.stdout or version.stderr,
                "inspect": inspect_value,
                "models": models.stdout,
                "x_skill_present": x_skill.exists(),
                "live_x_search_verified": False,
            },
            remediation=remediation
            + (
                ["Run the init X-search smoke test with source URLs before marking live X research ready."]
                if status == "pass"
                else []
            ),
        )


class AgmsgProbe(Probe):
    name = "agmsg"
    category = "communication"

    def run(self):
        home = Path.home()
        skill = home / ".agents" / "skills" / "agmsg"
        git_bash_candidates = [
            Path(r"C:\Program Files\Git\bin\bash.exe"),
            Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
            Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
        ]
        bash_path = shutil.which("bash")
        if os.name == "nt":
            selected = next((path for path in git_bash_candidates if path.exists()), None)
            bash_path = str(selected) if selected else bash_path
        installed = skill.exists()
        if installed and bash_path:
            return self.result(
                "pass",
                "agmsg skill and a Bash runtime were found",
                details={"skill_path": str(skill), "bash": bash_path},
            )
        remediation = []
        if not installed:
            remediation.append("Install agmsg with `npx agmsg`, then restart Codex/Claude/Grok sessions.")
        if not bash_path:
            remediation.append("Install Git for Windows and pin Git Bash instead of the WSL bash shim.")
        return self.result(
            "warn",
            "agmsg is optional but not fully ready",
            details={"skill_path": str(skill), "installed": installed, "bash": bash_path},
            remediation=remediation,
        )
