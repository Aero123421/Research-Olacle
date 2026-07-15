from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any

from .campaign import update_campaign_state
from .models import LabPaths
from .utils import atomic_write_json, iso_now, read_json

JOB_ID_RE = re.compile(r"^JOB-[A-Za-z0-9._-]+$")
GPU_RESOURCES = {"GPU0", "GPU1", "Kaggle", "SSH GPU", "Colab"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}


def _store_path(paths: LabPaths):
    return paths.runtime / "jobs.json"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _elapsed_hours(started_at: str | None, finished_at: str | None = None) -> float:
    start = _parse_time(started_at)
    if not start:
        return 0.0
    end = _parse_time(finished_at) or datetime.now(UTC)
    return max(0.0, (end - start).total_seconds() / 3600)


def load_jobs(paths: LabPaths) -> list[dict[str, Any]]:
    value = read_json(_store_path(paths), default={"schema_version": 1, "jobs": []})
    if not isinstance(value, dict) or not isinstance(value.get("jobs"), list):
        raise ValueError("runtime/jobs.json is malformed")
    return list(value["jobs"])


def _save(paths: LabPaths, jobs: list[dict[str, Any]]) -> None:
    paths.ensure_runtime()
    atomic_write_json(
        _store_path(paths),
        {"schema_version": 1, "updated_at": iso_now(), "jobs": jobs},
    )


def _get(jobs: list[dict[str, Any]], job_id: str) -> dict[str, Any]:
    for job in jobs:
        if job.get("job_id") == job_id:
            return job
    raise FileNotFoundError(f"Unknown job {job_id}")


def register_job(
    paths: LabPaths,
    *,
    campaign_id: str,
    name: str,
    resource: str,
    planned_hours: float,
    backend: str = "local_windows",
    command_summary: str | None = None,
    queue_after: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not (paths.campaigns / campaign_id / "CONTRACT.json").exists():
        raise FileNotFoundError(f"Unknown campaign {campaign_id}")
    if not name.strip():
        raise ValueError("Job name must not be empty")
    if planned_hours < 0:
        raise ValueError("planned_hours must be non-negative")
    job_id = job_id or f"JOB-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    if not JOB_ID_RE.match(job_id):
        raise ValueError("job_id must look like JOB-name")
    jobs = load_jobs(paths)
    if any(job.get("job_id") == job_id for job in jobs):
        raise FileExistsError(f"Job {job_id} already exists")
    if queue_after and not any(job.get("job_id") == queue_after for job in jobs):
        raise FileNotFoundError(f"queue_after references unknown job {queue_after}")
    now = iso_now()
    job = {
        "schema_version": 1,
        "job_id": job_id,
        "campaign_id": campaign_id,
        "name": name.strip(),
        "backend": backend,
        "resource": resource,
        "uses_gpu": resource in GPU_RESOURCES,
        "status": "queued",
        "queue_after": queue_after,
        "planned_hours": float(planned_hours),
        "actual_wall_hours": 0.0,
        "actual_gpu_hours": 0.0,
        "command_summary": command_summary,
        "progress": None,
        "created_at": now,
        "started_at": None,
        "last_heartbeat_at": None,
        "finished_at": None,
        "exit_code": None,
        "failure_summary": None,
    }
    jobs.append(job)
    _save(paths, jobs)
    return job


def start_job(paths: LabPaths, job_id: str) -> dict[str, Any]:
    jobs = load_jobs(paths)
    job = _get(jobs, job_id)
    if job["status"] == "running":
        return job
    if job["status"] in TERMINAL_STATES:
        raise ValueError(f"Job {job_id} is already {job['status']}")
    blocker = job.get("queue_after")
    if blocker:
        parent = _get(jobs, blocker)
        if parent.get("status") != "completed":
            raise ValueError(f"Job {job_id} is blocked by {blocker}")
    now = iso_now()
    job.update({"status": "running", "started_at": now, "last_heartbeat_at": now})
    _save(paths, jobs)
    return job


def heartbeat_job(
    paths: LabPaths,
    job_id: str,
    *,
    progress: str | None = None,
    actual_wall_hours: float | None = None,
    actual_gpu_hours: float | None = None,
) -> dict[str, Any]:
    jobs = load_jobs(paths)
    job = _get(jobs, job_id)
    if job.get("status") != "running":
        raise ValueError(f"Job {job_id} is not running")
    elapsed = _elapsed_hours(job.get("started_at"))
    job["actual_wall_hours"] = round(actual_wall_hours if actual_wall_hours is not None else elapsed, 6)
    if job.get("uses_gpu"):
        job["actual_gpu_hours"] = round(actual_gpu_hours if actual_gpu_hours is not None else elapsed, 6)
    elif actual_gpu_hours not in (None, 0, 0.0):
        raise ValueError("Cannot record GPU hours for a non-GPU resource")
    if progress is not None:
        job["progress"] = progress
    job["last_heartbeat_at"] = iso_now()
    _save(paths, jobs)
    return job


def finish_job(
    paths: LabPaths,
    job_id: str,
    *,
    status: str = "completed",
    exit_code: int | None = None,
    failure_summary: str | None = None,
    actual_wall_hours: float | None = None,
    actual_gpu_hours: float | None = None,
) -> dict[str, Any]:
    if status not in TERMINAL_STATES:
        raise ValueError(f"status must be one of {sorted(TERMINAL_STATES)}")
    jobs = load_jobs(paths)
    job = _get(jobs, job_id)
    if job.get("status") in TERMINAL_STATES:
        if job.get("status") == status:
            return job
        raise ValueError(f"Job {job_id} is already {job['status']}")
    now = iso_now()
    elapsed = _elapsed_hours(job.get("started_at"), now)
    job["actual_wall_hours"] = round(actual_wall_hours if actual_wall_hours is not None else elapsed, 6)
    if job.get("uses_gpu"):
        job["actual_gpu_hours"] = round(actual_gpu_hours if actual_gpu_hours is not None else elapsed, 6)
    job.update(
        {
            "status": status,
            "finished_at": now,
            "last_heartbeat_at": now,
            "exit_code": exit_code,
            "failure_summary": failure_summary,
        }
    )
    _save(paths, jobs)
    return job


def list_jobs(
    paths: LabPaths,
    *,
    campaign_id: str | None = None,
    status: str | None = None,
    resource: str | None = None,
) -> list[dict[str, Any]]:
    jobs = load_jobs(paths)
    if campaign_id:
        jobs = [job for job in jobs if job.get("campaign_id") == campaign_id]
    if status:
        jobs = [job for job in jobs if job.get("status") == status]
    if resource:
        jobs = [job for job in jobs if job.get("resource") == resource]
    return jobs


def gpu_queue(paths: LabPaths) -> list[dict[str, Any]]:
    jobs = [
        job for job in load_jobs(paths) if job.get("uses_gpu") and job.get("status") in {"queued", "running"}
    ]
    return sorted(
        jobs, key=lambda job: (0 if job.get("status") == "running" else 1, job.get("created_at", ""))
    )


def sync_campaign_resources(paths: LabPaths, campaign_id: str) -> dict[str, Any]:
    jobs = list_jobs(paths, campaign_id=campaign_id)
    wall = sum(float(job.get("actual_wall_hours", 0) or 0) for job in jobs)
    gpu = sum(float(job.get("actual_gpu_hours", 0) or 0) for job in jobs)
    running = [job for job in jobs if job.get("status") == "running"]
    queued = [job for job in jobs if job.get("status") == "queued"]
    patch: dict[str, Any] = {
        "resources": {
            "wall_hours_used": round(wall, 6),
            "gpu_hours_used": round(gpu, 6),
        },
    }
    if running:
        patch["status"] = "running"
        patch["current_action"] = "; ".join(
            f"{job['name']}: {job.get('progress') or 'running'}" for job in running
        )
    if queued:
        patch["next_actions"] = [f"Run {job['name']} ({job.get('resource')})" for job in queued[:3]]
    return update_campaign_state(paths, campaign_id, patch)
