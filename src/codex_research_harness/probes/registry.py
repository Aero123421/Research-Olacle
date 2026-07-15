from __future__ import annotations

from typing import Any

from ..models import LabPaths
from .agents import AgmsgProbe, ClaudeProbe, CodexProbe, GrokProbe
from .base import Probe
from .core import DiskProbe, GitProbe, PythonProbe, WindowsProbe
from .services import (
    BrowserProbe,
    ChatGPTProjectProbe,
    GitHubProbe,
    KaggleProbe,
    NvidiaGpuProbe,
    SecretHygieneProbe,
)


def build_probes(paths: LabPaths, config: dict[str, Any], profile: str = "full") -> list[Probe]:
    groups: dict[str, list[type[Probe]]] = {
        "quick": [PythonProbe, GitProbe, SecretHygieneProbe],
        "core": [PythonProbe, GitProbe, WindowsProbe, GitHubProbe, SecretHygieneProbe],
        "agents": [CodexProbe, ClaudeProbe, GrokProbe, AgmsgProbe, BrowserProbe, ChatGPTProjectProbe],
        "kaggle": [KaggleProbe, NvidiaGpuProbe, DiskProbe],
        "full": [
            PythonProbe,
            GitProbe,
            WindowsProbe,
            GitHubProbe,
            CodexProbe,
            ClaudeProbe,
            GrokProbe,
            AgmsgProbe,
            BrowserProbe,
            ChatGPTProjectProbe,
            KaggleProbe,
            NvidiaGpuProbe,
            DiskProbe,
            SecretHygieneProbe,
        ],
    }
    selected = groups.get(profile)
    if selected is None:
        raise ValueError(f"Unknown doctor profile: {profile}")
    return [probe_type(paths, config) for probe_type in selected]
