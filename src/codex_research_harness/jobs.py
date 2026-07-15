from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .campaign import update_campaign_state
from .config import load_compute_config, load_lab_config
from .locking import lab_lock
from .models import LabPaths
from .utils import atomic_write_json, iso_now, read_json

JOB_ID_RE = re.compile(r"^JOB-[A-Za-z0-9._-]+$")
GPU_RESOURCES = {"GPU0", "GPU1", "Kaggle", "SSH GPU", "Colab"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}


class ResourceAuthorizationError(RuntimeError):
    """Raised when a job would cross a configured compute boundary."""


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


def _campaign_documents(paths: LabPaths, campaign_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    directory = paths.campaigns / campaign_id
    contract = read_json(directory / "CONTRACT.json", default={})
    state = read_json(directory / "STATE.json", default={})
    if not contract:
        raise FileNotFoundError(f"Unknown campaign {campaign_id}")
    if not state:
        raise FileNotFoundError(f"Missing state for campaign {campaign_id}")
    return contract, state


def _projected_usage(
    jobs: list[dict[str, Any]],
    *,
    campaign_id: str,
    ignore_job_id: str | None = None,
) -> dict[str, float]:
    wall = 0.0
    gpu = 0.0
    cost = 0.0
    for job in jobs:
        if job.get("campaign_id") != campaign_id or job.get("job_id") == ignore_job_id:
            continue
        status = job.get("status")
        if status in TERMINAL_STATES:
            wall += float(job.get("actual_wall_hours", 0) or 0)
            gpu += float(job.get("actual_gpu_hours", 0) or 0)
            cost += float(job.get("actual_cost_jpy", 0) or 0)
        elif status in {"queued", "running"}:
            wall += max(
                float(job.get("planned_hours", 0) or 0),
                float(job.get("actual_wall_hours", 0) or 0),
            )
            if job.get("uses_gpu"):
                gpu += max(
                    float(job.get("planned_hours", 0) or 0),
                    float(job.get("actual_gpu_hours", 0) or 0),
                )
            cost += max(
                float(job.get("planned_cost_jpy", 0) or 0),
                float(job.get("actual_cost_jpy", 0) or 0),
            )
    return {"wall_hours": wall, "gpu_hours": gpu, "cost_jpy": cost}


def _local_day_gpu_hours(
    paths: LabPaths, jobs: list[dict[str, Any]], *, ignore_job_id: str | None = None
) -> float:
    lab = load_lab_config(paths)
    timezone_name = str(lab.get("lab", {}).get("timezone", "UTC"))
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception:
        timezone = UTC
    today = datetime.now(timezone).date()
    total = 0.0
    for job in jobs:
        if job.get("job_id") == ignore_job_id:
            continue
        if job.get("backend") != "local_windows" or not job.get("uses_gpu"):
            continue
        stamp = _parse_time(job.get("started_at") or job.get("created_at"))
        if not stamp or stamp.astimezone(timezone).date() != today:
            continue
        if job.get("status") in TERMINAL_STATES:
            total += float(job.get("actual_gpu_hours", 0) or 0)
        elif job.get("status") in {"queued", "running"}:
            total += max(
                float(job.get("planned_hours", 0) or 0),
                float(job.get("actual_gpu_hours", 0) or 0),
            )
    return total


def _monthly_paid_cost(
    paths: LabPaths, jobs: list[dict[str, Any]], *, ignore_job_id: str | None = None
) -> float:
    lab = load_lab_config(paths)
    timezone_name = str(lab.get("lab", {}).get("timezone", "UTC"))
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception:
        timezone = UTC
    now = datetime.now(timezone)
    total = 0.0
    for job in jobs:
        if job.get("job_id") == ignore_job_id:
            continue
        stamp = _parse_time(job.get("created_at"))
        if not stamp:
            continue
        local_stamp = stamp.astimezone(timezone)
        if (local_stamp.year, local_stamp.month) != (now.year, now.month):
            continue
        if job.get("status") in TERMINAL_STATES:
            total += float(job.get("actual_cost_jpy", 0) or 0)
        else:
            total += max(
                float(job.get("planned_cost_jpy", 0) or 0),
                float(job.get("actual_cost_jpy", 0) or 0),
            )
    return total


def _authorize_job(
    paths: LabPaths,
    jobs: list[dict[str, Any]],
    *,
    campaign_id: str,
    backend: str,
    resource: str,
    planned_hours: float,
    planned_cost_jpy: float,
    finalization: bool,
    ignore_job_id: str | None = None,
    check_running_capacity: bool = False,
    require_active_executor: bool = False,
) -> None:
    contract, state = _campaign_documents(paths, campaign_id)
    if contract.get("contract_status") != "ready":
        raise ResourceAuthorizationError(f"Campaign {campaign_id} does not have a ready Contract")
    if state.get("status") in {"completed", "stopped"}:
        raise ResourceAuthorizationError(f"Campaign {campaign_id} is already {state.get('status')}")
    if require_active_executor:
        executor = state.get("executor") if isinstance(state.get("executor"), dict) else {}
        lease = _parse_time(executor.get("lease_expires_at"))
        if state.get("status") not in {"executing", "running", "waiting", "validating", "reporting"}:
            raise ResourceAuthorizationError(
                f"Campaign {campaign_id} has no active Executor claim; claim it before starting jobs"
            )
        if not executor.get("claim_id") or not lease or lease <= datetime.now(UTC):
            raise ResourceAuthorizationError(f"Campaign {campaign_id} Executor claim is missing or expired")
    budget_status = state.get("budget_status", "within_budget")
    if budget_status == "exhausted":
        raise ResourceAuthorizationError(f"Campaign {campaign_id} has exhausted its resource budget")
    if budget_status == "finalization_only" and not finalization:
        raise ResourceAuthorizationError(
            f"Campaign {campaign_id} is in finalization-only mode; mark only confirmation/reporting jobs as finalization"
        )

    compute = load_compute_config(paths)
    backends = compute.get("backends", {})
    backend_config = backends.get(backend) if isinstance(backends, dict) else None
    if not isinstance(backend_config, dict) or backend_config.get("enabled") is not True:
        raise ResourceAuthorizationError(f"Compute backend {backend!r} is not enabled")

    uses_gpu = resource in GPU_RESOURCES
    projected = _projected_usage(jobs, campaign_id=campaign_id, ignore_job_id=ignore_job_id)
    durable_resources = state.get("resources", {}) if isinstance(state.get("resources"), dict) else {}
    accounted_wall = max(projected["wall_hours"], float(durable_resources.get("wall_hours_used", 0) or 0))
    accounted_gpu = max(projected["gpu_hours"], float(durable_resources.get("gpu_hours_used", 0) or 0))
    accounted_cost = max(projected["cost_jpy"], float(durable_resources.get("cost_jpy", 0) or 0))
    projected_wall = accounted_wall + planned_hours
    projected_gpu = accounted_gpu + (planned_hours if uses_gpu else 0.0)
    projected_cost = accounted_cost + planned_cost_jpy
    budget = contract.get("budget", {})
    limits = {
        "wall_hours": float(budget.get("wall_hours", 0) or 0),
        "gpu_hours": float(budget.get("gpu_hours", 0) or 0),
        "cost_jpy": float(budget.get("paid_compute_jpy", 0) or 0),
    }
    if limits["wall_hours"] > 0 and projected_wall > limits["wall_hours"] + 1e-9:
        raise ResourceAuthorizationError(
            f"Projected campaign wall time {projected_wall:.3f}h exceeds {limits['wall_hours']:.3f}h"
        )
    if uses_gpu and projected_gpu > limits["gpu_hours"] + 1e-9:
        raise ResourceAuthorizationError(
            f"Projected campaign GPU time {projected_gpu:.3f}h exceeds {limits['gpu_hours']:.3f}h"
        )
    if projected_cost > limits["cost_jpy"] + 1e-9:
        raise ResourceAuthorizationError(
            f"Projected campaign cost JPY {projected_cost:.0f} exceeds JPY {limits['cost_jpy']:.0f}"
        )

    local = compute.get("local", {})
    if uses_gpu and backend == "local_windows":
        daily_limit = float(local.get("max_gpu_hours_per_day", 0) or 0)
        projected_daily = _local_day_gpu_hours(paths, jobs, ignore_job_id=ignore_job_id) + planned_hours
        if daily_limit > 0 and projected_daily > daily_limit + 1e-9:
            raise ResourceAuthorizationError(
                f"Projected local GPU use today {projected_daily:.3f}h exceeds {daily_limit:.3f}h"
            )

    paid = compute.get("paid_compute", {})
    if planned_cost_jpy > 0:
        if paid.get("enabled") is not True:
            raise ResourceAuthorizationError("Paid compute is disabled")
        per_job = float(paid.get("per_job_hard_limit_jpy", 0) or 0)
        if per_job > 0 and planned_cost_jpy > per_job + 1e-9:
            raise ResourceAuthorizationError(
                f"Planned job cost JPY {planned_cost_jpy:.0f} exceeds per-job limit JPY {per_job:.0f}"
            )
        monthly = float(paid.get("monthly_hard_limit_jpy", 0) or 0)
        projected_month = _monthly_paid_cost(paths, jobs, ignore_job_id=ignore_job_id) + planned_cost_jpy
        if monthly > 0 and projected_month > monthly + 1e-9:
            raise ResourceAuthorizationError(
                f"Projected monthly paid-compute cost JPY {projected_month:.0f} exceeds JPY {monthly:.0f}"
            )

    if check_running_capacity and uses_gpu:
        running = [job for job in jobs if job.get("status") == "running" and job.get("uses_gpu")]
        if ignore_job_id:
            running = [job for job in running if job.get("job_id") != ignore_job_id]
        if any(job.get("resource") == resource for job in running):
            raise ResourceAuthorizationError(f"Physical resource {resource} is already in use")
        maximum = int(local.get("max_parallel_gpu_jobs", 1) or 1)
        if len(running) >= maximum:
            raise ResourceAuthorizationError(f"Maximum parallel GPU jobs ({maximum}) is already reached")


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
    planned_cost_jpy: float = 0.0,
    finalization: bool = False,
) -> dict[str, Any]:
    if not name.strip():
        raise ValueError("Job name must not be empty")
    if planned_hours < 0 or planned_cost_jpy < 0:
        raise ValueError("planned_hours and planned_cost_jpy must be non-negative")

    with lab_lock(paths, "jobs"):
        job_id = job_id or f"JOB-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        if not JOB_ID_RE.match(job_id):
            raise ValueError("job_id must look like JOB-name")
        jobs = load_jobs(paths)
        if any(job.get("job_id") == job_id for job in jobs):
            raise FileExistsError(f"Job {job_id} already exists")
        if queue_after and not any(job.get("job_id") == queue_after for job in jobs):
            raise FileNotFoundError(f"queue_after references unknown job {queue_after}")
        _authorize_job(
            paths,
            jobs,
            campaign_id=campaign_id,
            backend=backend,
            resource=resource,
            planned_hours=float(planned_hours),
            planned_cost_jpy=float(planned_cost_jpy),
            finalization=finalization,
        )
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
            "planned_cost_jpy": float(planned_cost_jpy),
            "finalization": bool(finalization),
            "actual_wall_hours": 0.0,
            "actual_gpu_hours": 0.0,
            "actual_cost_jpy": 0.0,
            "command_summary": command_summary,
            "progress": None,
            "stop_required": False,
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
    with lab_lock(paths, "jobs"):
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
        _authorize_job(
            paths,
            jobs,
            campaign_id=str(job["campaign_id"]),
            backend=str(job["backend"]),
            resource=str(job["resource"]),
            planned_hours=float(job.get("planned_hours", 0) or 0),
            planned_cost_jpy=float(job.get("planned_cost_jpy", 0) or 0),
            finalization=bool(job.get("finalization")),
            ignore_job_id=job_id,
            check_running_capacity=True,
            require_active_executor=True,
        )
        now = iso_now()
        job.update({"status": "running", "started_at": now, "last_heartbeat_at": now})
        _save(paths, jobs)
        result = dict(job)
    sync_campaign_resources(paths, str(result["campaign_id"]))
    return result


def _actual_limit_reasons(paths: LabPaths, jobs: list[dict[str, Any]], job: dict[str, Any]) -> list[str]:
    contract, _ = _campaign_documents(paths, str(job["campaign_id"]))
    projected = _projected_usage(jobs, campaign_id=str(job["campaign_id"]))
    budget = contract.get("budget", {})
    reasons: list[str] = []
    limits = {
        "wall_hours": float(budget.get("wall_hours", 0) or 0),
        "gpu_hours": float(budget.get("gpu_hours", 0) or 0),
        "cost_jpy": float(budget.get("paid_compute_jpy", 0) or 0),
    }
    if limits["wall_hours"] > 0 and projected["wall_hours"] > limits["wall_hours"] + 1e-9:
        reasons.append("campaign wall budget exceeded")
    if projected["gpu_hours"] > limits["gpu_hours"] + 1e-9:
        reasons.append("campaign GPU budget exceeded")
    if projected["cost_jpy"] > limits["cost_jpy"] + 1e-9:
        reasons.append("campaign cost budget exceeded")

    compute = load_compute_config(paths)
    local = compute.get("local", {})
    if job.get("backend") == "local_windows" and job.get("uses_gpu"):
        daily_limit = float(local.get("max_gpu_hours_per_day", 0) or 0)
        if daily_limit > 0 and _local_day_gpu_hours(paths, jobs) > daily_limit + 1e-9:
            reasons.append("local daily GPU limit exceeded")

    actual_cost = float(job.get("actual_cost_jpy", 0) or 0)
    if actual_cost > 0:
        paid = compute.get("paid_compute", {})
        per_job = float(paid.get("per_job_hard_limit_jpy", 0) or 0)
        if paid.get("enabled") is not True:
            reasons.append("paid compute is disabled")
        if per_job > 0 and actual_cost > per_job + 1e-9:
            reasons.append("per-job paid-compute limit exceeded")
        monthly = float(paid.get("monthly_hard_limit_jpy", 0) or 0)
        if monthly > 0 and _monthly_paid_cost(paths, jobs) > monthly + 1e-9:
            reasons.append("monthly paid-compute limit exceeded")
    return reasons


def heartbeat_job(
    paths: LabPaths,
    job_id: str,
    *,
    progress: str | None = None,
    actual_wall_hours: float | None = None,
    actual_gpu_hours: float | None = None,
    actual_cost_jpy: float | None = None,
) -> dict[str, Any]:
    limit_reasons: list[str] = []
    with lab_lock(paths, "jobs"):
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
        if actual_cost_jpy is not None:
            if actual_cost_jpy < 0:
                raise ValueError("actual_cost_jpy must be non-negative")
            job["actual_cost_jpy"] = float(actual_cost_jpy)
        if progress is not None:
            job["progress"] = progress
        job["last_heartbeat_at"] = iso_now()
        limit_reasons = _actual_limit_reasons(paths, jobs, job)
        if limit_reasons:
            job["stop_required"] = True
            job["progress"] = "HARD STOP REQUIRED: " + "; ".join(limit_reasons)
        _save(paths, jobs)
        result = dict(job)
    sync_campaign_resources(paths, str(result["campaign_id"]))
    if limit_reasons:
        raise ResourceAuthorizationError("; ".join(limit_reasons))
    return result


def finish_job(
    paths: LabPaths,
    job_id: str,
    *,
    status: str = "completed",
    exit_code: int | None = None,
    failure_summary: str | None = None,
    actual_wall_hours: float | None = None,
    actual_gpu_hours: float | None = None,
    actual_cost_jpy: float | None = None,
) -> dict[str, Any]:
    if status not in TERMINAL_STATES:
        raise ValueError(f"status must be one of {sorted(TERMINAL_STATES)}")
    with lab_lock(paths, "jobs"):
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
        if actual_cost_jpy is not None:
            if actual_cost_jpy < 0:
                raise ValueError("actual_cost_jpy must be non-negative")
            job["actual_cost_jpy"] = float(actual_cost_jpy)
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
        result = dict(job)
    sync_campaign_resources(paths, str(result["campaign_id"]))
    return result


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
    cost = sum(float(job.get("actual_cost_jpy", 0) or 0) for job in jobs)
    running = [job for job in jobs if job.get("status") == "running"]
    queued = [job for job in jobs if job.get("status") == "queued"]
    patch: dict[str, Any] = {
        "resources": {
            "wall_hours_used": round(wall, 6),
            "gpu_hours_used": round(gpu, 6),
            "cost_jpy": round(cost, 2),
        },
    }
    if running:
        patch["current_action"] = "; ".join(
            f"{job['name']}: {job.get('progress') or 'running'}" for job in running
        )
    if queued:
        patch["next_actions"] = [f"Run {job['name']} ({job.get('resource')})" for job in queued[:3]]
    return update_campaign_state(paths, campaign_id, patch)
