from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .utils import iso_now

ProbeStatus = Literal["pass", "warn", "fail", "skip"]


@dataclass(frozen=True)
class LabPaths:
    root: Path

    @property
    def lab(self) -> Path:
        return self.root / ".research-lab"

    @property
    def local(self) -> Path:
        return self.lab / "local"

    @property
    def research(self) -> Path:
        return self.root / "research"

    @property
    def setup(self) -> Path:
        return self.research / "setup"

    @property
    def strategy(self) -> Path:
        return self.research / "strategy"

    @property
    def campaigns(self) -> Path:
        return self.research / "campaigns"

    @property
    def consultations(self) -> Path:
        return self.research / "consultations"

    @property
    def runtime(self) -> Path:
        return self.root / "runtime"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def experiments(self) -> Path:
        return self.root / "experiments"

    def ensure_runtime(self) -> None:
        for path in (
            self.local,
            self.runtime,
            self.runtime / "context",
            self.runtime / "logs",
            self.runtime / "jobs",
            self.reports / "visuals",
            self.reports / "cockpit",
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class ProbeResult:
    name: str
    status: ProbeStatus
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    remediation: list[str] = field(default_factory=list)
    category: str = "core"
    checked_at: str = field(default_factory=iso_now)

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def blocking(self) -> bool:
        return self.status == "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
            "remediation": self.remediation,
            "category": self.category,
            "checked_at": self.checked_at,
        }


@dataclass
class DoctorReport:
    results: list[ProbeResult]
    generated_at: str = field(default_factory=iso_now)
    profile: str = "full"

    @property
    def counts(self) -> dict[str, int]:
        values = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
        for result in self.results:
            values[result.status] += 1
        return values

    def category_status(self, category: str) -> ProbeStatus:
        items = [item for item in self.results if item.category == category]
        if not items:
            return "skip"
        if any(item.status == "fail" for item in items):
            return "fail"
        if any(item.status == "warn" for item in items):
            return "warn"
        if all(item.status == "skip" for item in items):
            return "skip"
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "profile": self.profile,
            "counts": self.counts,
            "categories": {
                category: self.category_status(category)
                for category in sorted({item.category for item in self.results})
            },
            "results": [item.to_dict() for item in self.results],
        }
