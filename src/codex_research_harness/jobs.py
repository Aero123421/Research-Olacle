from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .campaign import (
    ACTIVE_CAMPAIGN_STATUSES,
    ExecutorClaimError,
    require_current_executor_claim,
    sync_campaign_accounting,
)
from .config import load_compute_config, load_lab_config
from .locking import lab_lock
from .models import LabPaths
from .utils import atomic_write_json, iso_now, read_json

JOB_ID_RE = re.compile(r"^JOB-[A-Za-z0-9._-]+$")
TERMINAL_STATES = {"completed", "failed", "cancelled"}
GPU_RESOURCE_KINDS = {"gpu", "remote_gpu"}

# Paid-compute safety must be backed by executable code, not a TOML assertion.
# Provider adapters are intentionally empty until a reviewed adapter can both
# cancel the remote workload and retrieve authoritative provider-side cost.
IMPLEMENTED_BACKEND_CONTROLS: dict[str, dict[str, bool]] = {}


class ResourceAuthorizationError(RuntimeError):
    """Raised when a Job would cross an ownership or compute boundary."""


def _store_path(paths: LabPaths):
    return paths.runtime / "jobs.json"


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
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
    paths: LabPaths,
    jobs: list[dict[str, Any]],
    *,
    ignore_job_id: str | None = None,
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
        # A queued Job has not selected a start day yet. Count its reservation
        # against today rather than the day on which it happened to be
        # registered; otherwise yesterday's queued work can bypass today's
        # local-GPU cap when another Job starts before it.
        if job.get("status") == "queued":
            stamp = datetime.now(UTC)
        else:
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
    paths: LabPaths,
    jobs: list[dict[str, Any]],
    *,
    ignore_job_id: str | None = None,
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


def _resource_definition(
    compute: dict[str, Any],
    *,
    resource: str,
    backend: str,
) -> dict[str, Any]:
    resources = compute.get("resources", {})
    definition = resources.get(resource) if isinstance(resources, dict) else None
    if not isinstance(definition, dict) or definition.get("enabled", True) is not True:
        raise ResourceAuthorizationError(
            f"Compute resource {resource!r} is not registered and enabled in compute.toml"
        )
    configured_backend = definition.get("backend")
    if configured_backend != backend:
        raise ResourceAuthorizationError(
            f"Compute resource {resource!r} belongs to backend {configured_backend!r}, not {backend!r}"
        )
    kind = definition.get("kind")
    if kind not in {"cpu", "gpu", "remote_gpu"}:
        raise ResourceAuthorizationError(f"Compute resource {resource!r} has unsupported kind {kind!r}")
    capacity = definition.get("capacity", 1)
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ResourceAuthorizationError(
            f"Compute resource {resource!r} must declare a positive integer capacity"
        )
    result = dict(definition)
    result["kind"] = kind
    result["capacity"] = capacity
    result["uses_gpu"] = kind in GPU_RESOURCE_KINDS
    return result


def _implemented_backend_control(backend_config: dict[str, Any]) -> dict[str, bool] | None:
    """Return reviewed code capabilities for a configured backend adapter.

    Configuration is intentionally not enough to authorize paid compute. The
    adapter name must resolve through this in-process registry and its safety
    capabilities must be explicit booleans.
    """

    control_name = backend_config.get("control_adapter")
    if not isinstance(control_name, str) or not control_name or control_name == "none":
        return None
    raw = IMPLEMENTED_BACKEND_CONTROLS.get(control_name)
    if not isinstance(raw, dict):
        return None
    return {
        "enforced_cancellation": raw.get("enforced_cancellation") is True,
        "provider_cost_metering": raw.get("provider_cost_metering") is True,
    }


def _current_claim(
    state: dict[str, Any],
    claim_id: str | None,
    *,
    required: bool,
) -> dict[str, Any] | None:
    active = state.get("status") in ACTIVE_CAMPAIGN_STATUSES
    if not active and not required:
        if claim_id:
            raise ResourceAuthorizationError(
                f"Campaign {state.get('campaign_id')} has no active Executor claim"
            )
        return None
    try:
        return require_current_executor_claim(state, claim_id)
    except ExecutorClaimError as exc:
        raise ResourceAuthorizationError(str(exc)) from exc


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
    claim_id: str | None,
    ignore_job_id: str | None = None,
    check_running_capacity: bool = False,
    require_active_executor: bool = False,
) -> dict[str, Any]:
    """Authorize a Job while the jobs and Campaign locks are both held."""

    contract, state = _campaign_documents(paths, campaign_id)
    if contract.get("contract_status") != "ready":
        raise ResourceAuthorizationError(f"Campaign {campaign_id} does not have a ready Contract")
    allowed_statuses = {"ready", *ACTIVE_CAMPAIGN_STATUSES}
    if state.get("status") not in allowed_statuses:
        raise ResourceAuthorizationError(
            f"Campaign {campaign_id} cannot authorize Jobs while {state.get('status')!r}"
        )

    claim = _current_claim(state, claim_id, required=require_active_executor)
    budget_status = state.get("budget_status", "within_budget")
    if budget_status == "exhausted":
        raise ResourceAuthorizationError(f"Campaign {campaign_id} has exhausted its resource budget")
    if budget_status == "finalization_only" and not finalization:
        raise ResourceAuthorizationError(
            f"Campaign {campaign_id} is in finalization-only mode; mark only "
            "confirmation/reporting jobs as finalization"
        )

    compute = load_compute_config(paths)
    backends = compute.get("backends", {})
    backend_config = backends.get(backend) if isinstance(backends, dict) else None
    if not isinstance(backend_config, dict) or backend_config.get("enabled") is not True:
        raise ResourceAuthorizationError(f"Compute backend {backend!r} is not enabled")
    backend_paid = backend_config.get("paid")
    if not isinstance(backend_paid, bool):
        raise ResourceAuthorizationError(
            f"Compute backend {backend!r} must explicitly declare paid = true or false"
        )
    resource_config = _resource_definition(compute, resource=resource, backend=backend)
    uses_gpu = bool(resource_config["uses_gpu"])

    projected = _projected_usage(jobs, campaign_id=campaign_id, ignore_job_id=ignore_job_id)
    durable_resources = state.get("resources", {}) if isinstance(state.get("resources"), dict) else {}
    accounted_wall = max(
        projected["wall_hours"],
        float(durable_resources.get("wall_hours_used", 0) or 0),
    )
    accounted_gpu = max(
        projected["gpu_hours"],
        float(durable_resources.get("gpu_hours_used", 0) or 0),
    )
    accounted_cost = max(
        projected["cost_jpy"],
        float(durable_resources.get("cost_jpy", 0) or 0),
    )
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
    if backend_paid and planned_cost_jpy <= 0:
        raise ResourceAuthorizationError(
            f"Paid backend {backend!r} requires a positive planned_cost_jpy estimate"
        )
    if backend_paid or planned_cost_jpy > 0:
        if paid.get("enabled") is not True:
            raise ResourceAuthorizationError("Paid compute is disabled")
        control = _implemented_backend_control(backend_config)
        if control is None:
            raise ResourceAuthorizationError(
                f"Paid backend {backend!r} has no implemented control adapter; "
                "configuration claims alone cannot authorize paid compute"
            )
        if paid.get("require_auto_shutdown") is True and (
            backend_config.get("cancellation_mode") != "enforced"
            or control.get("enforced_cancellation") is not True
        ):
            raise ResourceAuthorizationError(
                f"Paid backend {backend!r} does not provide enforced cancellation"
            )
        if paid.get("require_cost_metering") is True and (
            backend_config.get("cost_metering") is not True
            or control.get("provider_cost_metering") is not True
        ):
            raise ResourceAuthorizationError(
                f"Paid backend {backend!r} does not provide provider cost metering"
            )
        per_job = float(paid.get("per_job_hard_limit_jpy", 0) or 0)
        if per_job > 0 and planned_cost_jpy > per_job + 1e-9:
            raise ResourceAuthorizationError(
                f"Planned Job cost JPY {planned_cost_jpy:.0f} exceeds per-Job limit JPY {per_job:.0f}"
            )
        monthly = float(paid.get("monthly_hard_limit_jpy", 0) or 0)
        projected_month = _monthly_paid_cost(paths, jobs, ignore_job_id=ignore_job_id) + planned_cost_jpy
        if monthly > 0 and projected_month > monthly + 1e-9:
            raise ResourceAuthorizationError(
                f"Projected monthly paid-compute cost JPY {projected_month:.0f} exceeds JPY {monthly:.0f}"
            )

    if check_running_capacity:
        running = [job for job in jobs if job.get("status") == "running"]
        if ignore_job_id:
            running = [job for job in running if job.get("job_id") != ignore_job_id]
        same_resource = [job for job in running if job.get("resource") == resource]
        if len(same_resource) >= int(resource_config["capacity"]):
            raise ResourceAuthorizationError(f"Physical resource {resource} is already in use")
        if uses_gpu and backend == "local_windows":
            local_running = [
                job for job in running if job.get("backend") == "local_windows" and job.get("uses_gpu")
            ]
            maximum = int(local.get("max_parallel_gpu_jobs", 1) or 1)
            if len(local_running) >= maximum:
                raise ResourceAuthorizationError(
                    f"Maximum parallel local GPU Jobs ({maximum}) is already reached"
                )

    return {
        "claim": claim,
        "resource": resource_config,
        "backend": {**backend_config, "paid": backend_paid},
    }


def _validate_job_claim(job: dict[str, Any], claim: dict[str, Any]) -> None:
    bound_claim = job.get("executor_claim_id")
    bound_generation = job.get("executor_generation")
    if not bound_claim or bound_generation is None:
        raise ResourceAuthorizationError(
            f"Job {job.get('job_id')} is not fenced to an Executor claim; "
            "cancel or fail it with force-stale-claim before continuing"
        )
    if bound_claim != claim.get("claim_id") or bound_generation != claim.get("generation"):
        raise ResourceAuthorizationError(f"Job {job.get('job_id')} belongs to a superseded Executor claim")


def _bind_job(job: dict[str, Any], claim: dict[str, Any]) -> None:
    bound_claim = job.get("executor_claim_id")
    bound_generation = job.get("executor_generation")
    if bound_claim is not None or bound_generation is not None:
        _validate_job_claim(job, claim)
        return
    job["executor_claim_id"] = claim["claim_id"]
    job["executor_generation"] = claim["generation"]


def _new_cancellation(mode: str) -> dict[str, Any]:
    return {
        "state": "not_requested",
        "mode": mode,
        "requested_at": None,
        "confirmed_at": None,
        "reason": None,
        "confirmation_basis": None,
        "external_stop_confirmed": False,
        "external_stop_reference": None,
    }


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
    claim_id: str | None = None,
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
        if queue_after:
            parent = _get(jobs, queue_after)
            if parent.get("campaign_id") != campaign_id:
                raise ValueError("queue_after must reference a Job in the same Campaign")
        with lab_lock(paths, f"campaign-{campaign_id}"):
            authorization = _authorize_job(
                paths,
                jobs,
                campaign_id=campaign_id,
                backend=backend,
                resource=resource,
                planned_hours=float(planned_hours),
                planned_cost_jpy=float(planned_cost_jpy),
                finalization=finalization,
                claim_id=claim_id,
            )
            claim = authorization["claim"]
            resource_config = authorization["resource"]
            backend_config = authorization["backend"]
            now = iso_now()
            job = {
                "schema_version": 1,
                "job_id": job_id,
                "campaign_id": campaign_id,
                "name": name.strip(),
                "backend": backend,
                "backend_paid": bool(backend_config["paid"]),
                "resource": resource,
                "resource_kind": resource_config["kind"],
                "uses_gpu": bool(resource_config["uses_gpu"]),
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
                # Kept for backward compatibility. The structured cancellation
                # record is authoritative and distinguishes request from stop.
                "stop_required": False,
                "cancellation": _new_cancellation(
                    str(backend_config.get("cancellation_mode", "cooperative"))
                ),
                "control_adapter": (
                    backend_config.get("control_adapter")
                    if backend_config.get("control_adapter") not in {None, "", "none"}
                    else None
                ),
                "created_by_claim_id": claim.get("claim_id") if claim else None,
                "created_by_generation": claim.get("generation") if claim else None,
                "executor_claim_id": claim.get("claim_id") if claim else None,
                "executor_generation": claim.get("generation") if claim else None,
                "created_at": now,
                "started_at": None,
                "last_heartbeat_at": None,
                "finished_at": None,
                "exit_code": None,
                "failure_summary": None,
            }
            jobs.append(job)
            _save(paths, jobs)
            return dict(job)


def start_job(paths: LabPaths, job_id: str, *, claim_id: str | None) -> dict[str, Any]:
    with lab_lock(paths, "jobs"):
        jobs = load_jobs(paths)
        job = _get(jobs, job_id)
        campaign_id = str(job["campaign_id"])
        with lab_lock(paths, f"campaign-{campaign_id}"):
            if job["status"] in TERMINAL_STATES:
                raise ValueError(f"Job {job_id} is already {job['status']}")
            contract, state = _campaign_documents(paths, campaign_id)
            del contract
            claim = _current_claim(state, claim_id, required=True)
            assert claim is not None
            if job["status"] == "running":
                _validate_job_claim(job, claim)
                return dict(job)
            if job["status"] != "queued":
                raise ValueError(f"Job {job_id} cannot start from {job['status']!r}")
            blocker = job.get("queue_after")
            if blocker:
                parent = _get(jobs, blocker)
                if parent.get("status") != "completed":
                    raise ValueError(f"Job {job_id} is blocked by {blocker}")
            authorization = _authorize_job(
                paths,
                jobs,
                campaign_id=campaign_id,
                backend=str(job["backend"]),
                resource=str(job["resource"]),
                planned_hours=float(job.get("planned_hours", 0) or 0),
                planned_cost_jpy=float(job.get("planned_cost_jpy", 0) or 0),
                finalization=bool(job.get("finalization")),
                claim_id=claim_id,
                ignore_job_id=job_id,
                check_running_capacity=True,
                require_active_executor=True,
            )
            authorized_claim = authorization["claim"]
            assert authorized_claim is not None
            _bind_job(job, authorized_claim)
            now = iso_now()
            job.update({"status": "running", "started_at": now, "last_heartbeat_at": now})
            _save(paths, jobs)
            result = dict(job)
    sync_campaign_resources(paths, str(result["campaign_id"]))
    return result


def _actual_limit_reasons(
    paths: LabPaths,
    jobs: list[dict[str, Any]],
    job: dict[str, Any],
) -> list[str]:
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
    planned_cost = float(job.get("planned_cost_jpy", 0) or 0)
    paid = compute.get("paid_compute", {})
    backends = compute.get("backends", {})
    backend = backends.get(job.get("backend"), {}) if isinstance(backends, dict) else {}
    configured_paid = backend.get("paid") is True if isinstance(backend, dict) else False
    backend_paid = configured_paid or job.get("backend_paid") is True
    if backend_paid or planned_cost > 0 or actual_cost > 0:
        if backend_paid and planned_cost <= 0:
            reasons.append("paid backend has no positive planned cost estimate")
        control = _implemented_backend_control(backend) if isinstance(backend, dict) else None
        per_job = float(paid.get("per_job_hard_limit_jpy", 0) or 0)
        if paid.get("enabled") is not True:
            reasons.append("paid compute is disabled")
        if control is None:
            reasons.append("paid backend lacks an implemented control adapter")
        if paid.get("require_auto_shutdown") is True and (
            backend.get("cancellation_mode") != "enforced"
            or not control
            or control.get("enforced_cancellation") is not True
        ):
            reasons.append("paid backend lacks enforced cancellation")
        if paid.get("require_cost_metering") is True and (
            backend.get("cost_metering") is not True
            or not control
            or control.get("provider_cost_metering") is not True
        ):
            reasons.append("paid backend lacks provider cost metering")
        if per_job > 0 and actual_cost > per_job + 1e-9:
            reasons.append("per-Job paid-compute limit exceeded")
        monthly = float(paid.get("monthly_hard_limit_jpy", 0) or 0)
        if monthly > 0 and _monthly_paid_cost(paths, jobs) > monthly + 1e-9:
            reasons.append("monthly paid-compute limit exceeded")
    return reasons


def _authorized_bound_claim(
    paths: LabPaths,
    job: dict[str, Any],
    claim_id: str | None,
) -> dict[str, Any]:
    _, state = _campaign_documents(paths, str(job["campaign_id"]))
    claim = _current_claim(state, claim_id, required=True)
    assert claim is not None
    _validate_job_claim(job, claim)
    return claim


def _update_actual_usage(
    job: dict[str, Any],
    *,
    actual_wall_hours: float | None,
    actual_gpu_hours: float | None,
    actual_cost_jpy: float | None,
    finished_at: str | None = None,
) -> None:
    elapsed = _elapsed_hours(job.get("started_at"), finished_at)
    wall = actual_wall_hours if actual_wall_hours is not None else elapsed
    if wall < 0:
        raise ValueError("actual_wall_hours must be non-negative")
    previous_wall = float(job.get("actual_wall_hours", 0) or 0)
    if wall + 1e-9 < previous_wall:
        raise ValueError("actual_wall_hours cannot decrease")
    job["actual_wall_hours"] = round(wall, 6)
    if job.get("uses_gpu"):
        gpu = actual_gpu_hours if actual_gpu_hours is not None else elapsed
        if gpu < 0:
            raise ValueError("actual_gpu_hours must be non-negative")
        previous_gpu = float(job.get("actual_gpu_hours", 0) or 0)
        if gpu + 1e-9 < previous_gpu:
            raise ValueError("actual_gpu_hours cannot decrease")
        job["actual_gpu_hours"] = round(gpu, 6)
    elif actual_gpu_hours not in (None, 0, 0.0):
        raise ValueError("Cannot record GPU hours for a non-GPU resource")
    if actual_cost_jpy is not None:
        if actual_cost_jpy < 0:
            raise ValueError("actual_cost_jpy must be non-negative")
        previous_cost = float(job.get("actual_cost_jpy", 0) or 0)
        if actual_cost_jpy + 1e-9 < previous_cost:
            raise ValueError("actual_cost_jpy cannot decrease")
        job["actual_cost_jpy"] = float(actual_cost_jpy)


def _request_cancellation(job: dict[str, Any], reasons: list[str]) -> None:
    now = iso_now()
    cancellation = job.get("cancellation")
    if not isinstance(cancellation, dict):
        cancellation = _new_cancellation("cooperative")
    cancellation = dict(cancellation)
    if cancellation.get("state") == "not_requested":
        cancellation["requested_at"] = now
    cancellation.update({"state": "requested", "reason": "; ".join(reasons)})
    job["cancellation"] = cancellation
    job["stop_required"] = True
    job["progress"] = "CANCELLATION REQUESTED: " + "; ".join(reasons)


def _validate_force_stale_reconciliation(state: dict[str, Any], job: dict[str, Any]) -> None:
    """Reject the recovery bypass while the Job's owning claim is still live."""

    if state.get("status") not in ACTIVE_CAMPAIGN_STATUSES:
        return
    executor = state.get("executor") if isinstance(state.get("executor"), dict) else {}
    expiry = _parse_time(executor.get("lease_expires_at"))
    if not expiry or expiry <= datetime.now(UTC):
        return

    bound_claim = job.get("executor_claim_id")
    bound_generation = job.get("executor_generation")
    current_generation = executor.get("generation")
    if bound_claim == executor.get("claim_id") and bound_generation == current_generation:
        raise ResourceAuthorizationError(
            f"Job {job.get('job_id')} is owned by the current live Executor claim; "
            "force_stale_claim is only for expired, superseded, or unowned Jobs"
        )
    if bound_claim is None and bound_generation is None:
        raise ResourceAuthorizationError(
            f"Job {job.get('job_id')} is unbound while the Campaign has a live Executor; "
            "start or reconcile it through the current claim"
        )


def heartbeat_job(
    paths: LabPaths,
    job_id: str,
    *,
    claim_id: str | None,
    progress: str | None = None,
    actual_wall_hours: float | None = None,
    actual_gpu_hours: float | None = None,
    actual_cost_jpy: float | None = None,
) -> dict[str, Any]:
    limit_reasons: list[str] = []
    with lab_lock(paths, "jobs"):
        jobs = load_jobs(paths)
        job = _get(jobs, job_id)
        campaign_id = str(job["campaign_id"])
        with lab_lock(paths, f"campaign-{campaign_id}"):
            if job.get("status") != "running":
                raise ValueError(f"Job {job_id} is not running")
            _authorized_bound_claim(paths, job, claim_id)
            _update_actual_usage(
                job,
                actual_wall_hours=actual_wall_hours,
                actual_gpu_hours=actual_gpu_hours,
                actual_cost_jpy=actual_cost_jpy,
            )
            if progress is not None:
                job["progress"] = progress
            job["last_heartbeat_at"] = iso_now()
            limit_reasons = _actual_limit_reasons(paths, jobs, job)
            if limit_reasons:
                _request_cancellation(job, limit_reasons)
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
    claim_id: str | None = None,
    status: str = "completed",
    exit_code: int | None = None,
    failure_summary: str | None = None,
    actual_wall_hours: float | None = None,
    actual_gpu_hours: float | None = None,
    actual_cost_jpy: float | None = None,
    force_stale_claim: bool = False,
    external_stop_confirmed: bool = False,
    external_stop_reference: str | None = None,
) -> dict[str, Any]:
    if status not in TERMINAL_STATES:
        raise ValueError(f"status must be one of {sorted(TERMINAL_STATES)}")
    if status in {"failed", "cancelled"} and not failure_summary:
        raise ValueError(f"{status} Jobs require failure_summary for the audit trail")
    if force_stale_claim and status not in {"failed", "cancelled"}:
        raise ValueError("force_stale_claim may only fail or cancel a Job")
    if external_stop_reference is not None:
        if not isinstance(external_stop_reference, str) or not external_stop_reference.strip():
            raise ValueError("external_stop_reference must be a non-empty string")
        external_stop_reference = external_stop_reference.strip()
    if external_stop_confirmed and not external_stop_reference:
        raise ValueError("external_stop_confirmed requires external_stop_reference")
    if external_stop_reference and not external_stop_confirmed:
        raise ValueError("external_stop_reference requires external_stop_confirmed")
    stop_attestation_allowed = status == "cancelled" or (force_stale_claim and status == "failed")
    if not stop_attestation_allowed and (external_stop_confirmed or external_stop_reference):
        raise ValueError(
            "external stop confirmation is valid for cancelled Jobs or force-reconciled failed Jobs"
        )

    with lab_lock(paths, "jobs"):
        jobs = load_jobs(paths)
        job = _get(jobs, job_id)
        campaign_id = str(job["campaign_id"])
        with lab_lock(paths, f"campaign-{campaign_id}"):
            _, campaign_state = _campaign_documents(paths, campaign_id)
            previous_status = str(job.get("status"))
            if previous_status in TERMINAL_STATES:
                if previous_status == status:
                    return dict(job)
                raise ValueError(f"Job {job_id} is already {previous_status}")
            if force_stale_claim:
                _validate_force_stale_reconciliation(campaign_state, job)
            else:
                _authorized_bound_claim(paths, job, claim_id)
                if status == "completed" and previous_status != "running":
                    raise ValueError(f"Job {job_id} must be running before it can complete")
            if previous_status == "running" and (status == "cancelled" or force_stale_claim):
                if not external_stop_confirmed or not external_stop_reference:
                    raise ValueError(
                        "Terminating a running Job through cancellation or stale-claim recovery "
                        "requires external stop confirmation and an auditable "
                        "external_stop_reference"
                    )
            if (
                previous_status == "running"
                and status == "failed"
                and not force_stale_claim
                and exit_code is None
            ):
                raise ValueError(
                    "Failing a running Job requires an observed process exit_code; "
                    "use cancellation with external stop confirmation when termination "
                    "cannot be observed directly"
                )

            now = iso_now()
            _update_actual_usage(
                job,
                actual_wall_hours=actual_wall_hours,
                actual_gpu_hours=actual_gpu_hours,
                actual_cost_jpy=actual_cost_jpy,
                finished_at=now,
            )
            cancellation = job.get("cancellation")
            if not isinstance(cancellation, dict):
                cancellation = _new_cancellation("cooperative")
            cancellation = {**_new_cancellation(str(cancellation.get("mode", "cooperative"))), **cancellation}
            if status == "cancelled" or (force_stale_claim and previous_status == "running"):
                confirmation_basis = (
                    "external_stop_reference" if previous_status == "running" else "never_started"
                )
                cancellation.update(
                    {
                        "state": "confirmed",
                        "confirmed_at": now,
                        "confirmation_basis": confirmation_basis,
                        "external_stop_confirmed": bool(external_stop_confirmed),
                        "external_stop_reference": external_stop_reference,
                    }
                )
                job["stop_required"] = False
            elif cancellation.get("state") == "requested":
                confirmation_basis = (
                    f"process_exit_code:{exit_code}"
                    if status == "failed" and exit_code is not None
                    else f"terminal_status:{status}"
                )
                cancellation.update(
                    {
                        "state": "confirmed",
                        "confirmed_at": now,
                        "confirmation_basis": confirmation_basis,
                        "external_stop_confirmed": False,
                        "external_stop_reference": None,
                    }
                )
                job["stop_required"] = False
            job["cancellation"] = cancellation
            job.update(
                {
                    "status": status,
                    "finished_at": now,
                    "last_heartbeat_at": now,
                    "exit_code": exit_code,
                    "failure_summary": failure_summary,
                    "force_reconciled": bool(force_stale_claim),
                    "force_reconciled_at": now if force_stale_claim else None,
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
        jobs,
        key=lambda job: (0 if job.get("status") == "running" else 1, job.get("created_at", "")),
    )


def sync_campaign_resources(paths: LabPaths, campaign_id: str) -> dict[str, Any]:
    with lab_lock(paths, "jobs"):
        jobs = [job for job in load_jobs(paths) if job.get("campaign_id") == campaign_id]
    wall = sum(float(job.get("actual_wall_hours", 0) or 0) for job in jobs)
    gpu = sum(float(job.get("actual_gpu_hours", 0) or 0) for job in jobs)
    cost = sum(float(job.get("actual_cost_jpy", 0) or 0) for job in jobs)
    running = [job for job in jobs if job.get("status") == "running"]
    queued = [job for job in jobs if job.get("status") == "queued"]
    current_action = None
    next_actions = None
    if running:
        current_action = "; ".join(f"{job['name']}: {job.get('progress') or 'running'}" for job in running)
    if queued:
        next_actions = [f"Run {job['name']} ({job.get('resource')})" for job in queued[:3]]
    return sync_campaign_accounting(
        paths,
        campaign_id,
        resources={
            "wall_hours_used": round(wall, 6),
            "gpu_hours_used": round(gpu, 6),
            "cost_jpy": round(cost, 2),
        },
        current_action=current_action,
        next_actions=next_actions,
    )
