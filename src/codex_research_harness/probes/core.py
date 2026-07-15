from __future__ import annotations

import os
import platform
import shutil
import sys

from .base import Probe


class PythonProbe(Probe):
    name = "python"
    category = "core"

    def run(self):
        version = sys.version_info
        status = "pass" if version >= (3, 11) else "fail"
        return self.result(
            status,
            f"Python {platform.python_version()} at {sys.executable}",
            details={
                "version": platform.python_version(),
                "executable": sys.executable,
                "platform": platform.platform(),
            },
            remediation=[] if status == "pass" else ["Install Python 3.11 or later."],
        )


class GitProbe(Probe):
    name = "git"
    category = "core"

    def run(self):
        if not self.command_exists("git"):
            return self.result(
                "fail", "Git is not installed", remediation=["Install Git for Windows from git-scm.com."]
            )
        version = self.command(["git", "--version"])
        repo = self.command(["git", "rev-parse", "--show-toplevel"])
        remote = self.command(["git", "remote", "get-url", "origin"])
        branch = self.command(["git", "branch", "--show-current"])
        status = "pass" if version.ok and repo.ok else "fail"
        summary = version.stdout if version.ok else "Git command failed"
        if repo.ok:
            summary += f"; repository {repo.stdout}"
        return self.result(
            status,
            summary,
            details={
                "version": version.stdout,
                "repository": repo.stdout,
                "origin": remote.stdout if remote.ok else None,
                "branch": branch.stdout if branch.ok else None,
            },
            remediation=[] if status == "pass" else ["Open the cloned repository and rerun the doctor."],
        )


class DiskProbe(Probe):
    name = "disk"
    category = "compute"

    def run(self):
        usage = shutil.disk_usage(self.paths.root)
        free_gb = usage.free / (1024**3)
        threshold = float(self.config.get("compute", {}).get("minimum_free_disk_gb", 20))
        status = "pass" if free_gb >= threshold else "warn"
        return self.result(
            status,
            f"{free_gb:.1f} GiB free on repository volume",
            details={
                "total_gib": round(usage.total / (1024**3), 2),
                "used_gib": round(usage.used / (1024**3), 2),
                "free_gib": round(free_gb, 2),
                "minimum_gib": threshold,
            },
            remediation=[] if status == "pass" else ["Free disk space or move artifacts to a larger volume."],
        )


class WindowsProbe(Probe):
    name = "windows-host"
    category = "core"

    def run(self):
        is_windows = os.name == "nt"
        if is_windows:
            return self.result(
                "pass",
                f"Native Windows host detected ({platform.release()})",
                details={"platform": platform.platform()},
            )
        return self.result(
            "warn",
            "Current doctor run is not on Windows; Windows scripts are validated by CI",
            details={"platform": platform.platform()},
            remediation=[
                "Run scripts/bootstrap.ps1 on the Windows research host before autonomous research."
            ],
        )
