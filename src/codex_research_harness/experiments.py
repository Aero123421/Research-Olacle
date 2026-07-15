from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .locking import lab_lock
from .models import LabPaths
from .schema import validate_experiment, validate_or_raise
from .utils import iso_now, safe_relpath


def _hash_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def register_experiment(paths: LabPaths, value: dict[str, Any]) -> dict[str, Any]:
    value = dict(value)
    validate_or_raise(value, validate_experiment)
    campaign_dir = paths.campaigns / value["campaign_id"]
    if not campaign_dir.exists():
        raise ValueError(f"Unknown campaign {value['campaign_id']}")

    value.setdefault("recorded_at", iso_now())
    artifacts = []
    for raw in value.get("artifacts", []):
        if isinstance(raw, str):
            candidate = Path(raw)
            path = candidate if candidate.is_absolute() else paths.root / candidate
            relative = safe_relpath(path, paths.root)
            artifacts.append(
                {
                    "path": relative,
                    "exists": path.exists(),
                    "size_bytes": path.stat().st_size if path.is_file() else None,
                    "sha256": (
                        _hash_file(path) if path.is_file() and path.stat().st_size <= 1_000_000_000 else None
                    ),
                }
            )
        elif isinstance(raw, dict):
            artifacts.append(dict(raw))
    value["artifacts"] = artifacts

    with lab_lock(paths, "experiments-index"):
        existing = {item.get("experiment_id"): item for item in read_experiments(paths)}
        experiment_id = value["experiment_id"]
        if experiment_id in existing:
            if existing[experiment_id] == value:
                return existing[experiment_id]
            raise ValueError(f"Experiment {experiment_id} is already registered; records are append-only")
        index = paths.experiments / "index.jsonl"
        index.parent.mkdir(parents=True, exist_ok=True)
        with index.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
        return value


def read_experiments(paths: LabPaths) -> list[dict[str, Any]]:
    index = paths.experiments / "index.jsonl"
    if not index.exists():
        return []
    values = []
    seen: set[str] = set()
    with index.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid experiments/index.jsonl line {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Invalid experiments/index.jsonl line {line_number}: expected object")
            experiment_id = value.get("experiment_id")
            if experiment_id in seen:
                raise ValueError(f"Duplicate experiment_id {experiment_id!r} at line {line_number}")
            if isinstance(experiment_id, str):
                seen.add(experiment_id)
            values.append(value)
    return values
