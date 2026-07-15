from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..models import LabPaths, ProbeResult
from ..utils import CommandResult, run_command


class Probe(ABC):
    name: str
    category: str = "core"

    def __init__(self, paths: LabPaths, config: dict[str, Any]) -> None:
        self.paths = paths
        self.config = config

    @abstractmethod
    def run(self) -> ProbeResult:
        raise NotImplementedError

    def command_exists(self, name: str) -> bool:
        return shutil.which(name) is not None

    def command(
        self,
        args: Sequence[str],
        *,
        timeout: float = 15.0,
        cwd: Path | None = None,
    ) -> CommandResult:
        return run_command(args, timeout=timeout, cwd=cwd or self.paths.root)

    def result(
        self,
        status: str,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        remediation: list[str] | None = None,
    ) -> ProbeResult:
        return ProbeResult(
            name=self.name,
            status=status,  # type: ignore[arg-type]
            summary=summary,
            details=details or {},
            remediation=remediation or [],
            category=self.category,
        )
