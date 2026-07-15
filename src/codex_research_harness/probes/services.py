from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from ..utils import read_json, read_toml
from .base import Probe


class GitHubProbe(Probe):
    name = "github-cli"
    category = "github"

    def run(self):
        if not self.command_exists("gh"):
            return self.result(
                "fail",
                "GitHub CLI (`gh`) was not found",
                remediation=[
                    "Install GitHub CLI for Windows, then run `gh auth login` and `gh auth refresh -s project`."
                ],
            )
        version = self.command(["gh", "--version"])
        auth = self.command(["gh", "auth", "status"], timeout=20)
        repo = self.command(
            ["gh", "repo", "view", "--json", "nameWithOwner,url,defaultBranchRef"], timeout=20
        )
        auth_text = "\n".join([auth.stdout, auth.stderr])
        project_scope = bool(re.search(r"\bproject\b", auth_text, re.IGNORECASE))
        status = "pass" if auth.ok and repo.ok else "fail"
        remediation = []
        if not auth.ok:
            remediation.append("Run `gh auth login`.")
        if auth.ok and not project_scope:
            remediation.append("Run `gh auth refresh -s project` before creating the research dashboard.")
            if status == "pass":
                status = "warn"
        return self.result(
            status,
            "GitHub CLI is connected to the repository"
            if repo.ok
            else "GitHub authentication or repository access failed",
            details={
                "version": version.stdout.splitlines()[0] if version.stdout else None,
                "auth": auth_text,
                "project_scope_detected": project_scope,
                "repo": repo.stdout if repo.ok else repo.stderr,
            },
            remediation=remediation,
        )


class KaggleProbe(Probe):
    name = "kaggle-cli"
    category = "kaggle"

    def run(self):
        if not self.command_exists("kaggle"):
            return self.result(
                "warn",
                "Kaggle CLI was not found; non-Kaggle research can continue",
                remediation=["Install the official Kaggle CLI when running a Kaggle project."],
            )
        version = self.command(["kaggle", "--version"])
        entered = self.command(
            ["kaggle", "competitions", "list", "--group", "entered", "--page-size", "1"], timeout=30
        )
        status = "pass" if version.ok and entered.ok else "warn"
        return self.result(
            status,
            "Kaggle CLI is authenticated"
            if entered.ok
            else "Kaggle CLI is installed but authentication/access needs attention",
            details={"version": version.stdout, "safe_read_test": entered.stdout or entered.stderr},
            remediation=[]
            if entered.ok
            else [
                "Run `kaggle auth login` or configure a Kaggle token, then accept the competition rules in the browser."
            ],
        )


class NvidiaGpuProbe(Probe):
    name = "nvidia-gpu"
    category = "compute"

    def run(self):
        if not self.command_exists("nvidia-smi"):
            return self.result(
                "warn",
                "No NVIDIA GPU was detected through nvidia-smi",
                remediation=[
                    "Use CPU/remote compute, or install the NVIDIA driver on the Windows research host."
                ],
            )
        query = self.command(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.free,utilization.gpu,driver_version",
                "--format=csv,noheader,nounits",
            ],
            timeout=15,
        )
        if not query.ok:
            return self.result(
                "warn", "nvidia-smi exists but the GPU query failed", details={"error": query.stderr}
            )
        devices = []
        for line in query.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 6:
                devices.append(
                    {
                        "index": parts[0],
                        "name": parts[1],
                        "memory_total_mib": parts[2],
                        "memory_free_mib": parts[3],
                        "utilization_percent": parts[4],
                        "driver_version": parts[5],
                    }
                )
        return self.result("pass", f"Detected {len(devices)} NVIDIA GPU(s)", details={"devices": devices})


class BrowserProbe(Probe):
    name = "browser-mode"
    category = "chatgpt"

    def run(self):
        local = read_toml(self.paths.local / "browser.toml")
        mode = local.get("browser", {}).get("mode") if isinstance(local.get("browser"), dict) else None
        chrome_candidates = [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        chrome = next((str(path) for path in chrome_candidates if path.exists()), shutil.which("chrome"))
        if mode in {"built_in", "chrome"}:
            status = "pass" if mode == "built_in" or chrome else "warn"
            summary = f"Configured browser mode: {mode}"
            remediation = (
                []
                if status == "pass"
                else ["Install Chrome or select the Codex built-in browser during init."]
            )
            return self.result(
                status, summary, details={"mode": mode, "chrome": chrome}, remediation=remediation
            )
        return self.result(
            "warn",
            "Browser mode has not been selected",
            details={"chrome": chrome},
            remediation=["Run `researchctl init` and choose Codex built-in browser or Chrome."],
        )


class ChatGPTProjectProbe(Probe):
    name = "chatgpt-project"
    category = "chatgpt"

    def run(self):
        state = read_json(self.paths.local / "chatgpt.json", default={})
        if not isinstance(state, dict) or not state.get("project_url"):
            return self.result(
                "warn",
                "The dedicated ChatGPT research project has not been initialized",
                remediation=["Use the `chatgpt-research-partner` skill after choosing a browser mode."],
            )
        verified = bool(state.get("last_verified_at")) and state.get("status") == "ready"
        status = "pass" if verified else "warn"
        return self.result(
            status,
            "ChatGPT research project is configured"
            if verified
            else "ChatGPT project exists but needs browser verification",
            details={
                "project_name": state.get("project_name"),
                "project_url": state.get("project_url"),
                "browser_mode": state.get("browser_mode"),
                "model_label": state.get("selected_model_label"),
                "last_verified_at": state.get("last_verified_at"),
            },
            remediation=[]
            if verified
            else [
                "Open the saved project URL, verify login and the configured Pro model, then record verification."
            ],
        )


class SecretHygieneProbe(Probe):
    name = "secret-hygiene"
    category = "security"

    PATTERNS = {
        "openai_api_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        "github_pat": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        "classic_github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
        "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    }
    SKIP_DIRS = {".git", ".venv", "venv", "runtime", "artifacts", "__pycache__"}

    def run(self):
        findings: list[dict[str, str]] = []
        for path in self.paths.root.rglob("*"):
            if not path.is_file() or any(part in self.SKIP_DIRS for part in path.parts):
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for name, pattern in self.PATTERNS.items():
                if pattern.search(text):
                    findings.append({"path": str(path.relative_to(self.paths.root)), "pattern": name})
        if findings:
            return self.result(
                "fail",
                f"Found {len(findings)} potential secret(s)",
                details={"findings": findings},
                remediation=[
                    "Remove credentials from the repository and rotate any exposed secret before continuing."
                ],
            )
        return self.result("pass", "No common secret patterns were found in tracked source files")
