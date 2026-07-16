# ADR-0008: Exclusive Campaign execution and fail-closed resource boundaries

Status: accepted

## Context

Planner, Director monitoring, Goal Mode, and compute workers can operate in
parallel. File existence and dashboard warnings cannot prevent two Executors
from owning one Campaign, a stale process from continuing to write, two Jobs from
using one GPU, or an external workload from crossing a budget. A previous
"hard-stop marker" could also be misread as proof that an external process had
actually stopped.

## Decision

- Shared IDs and mutable ledgers use repository-local cross-platform locks.
- A ready Campaign must pass Context Pack integrity validation and complete an
  atomic claim before execution.
- The claim records owner, session, worktree, heartbeat, lease, and monotonic
  generation/fencing token.
- Every active Campaign write and compute Job operation presents the exact current
  claim; Jobs persist the claim ID and generation that own them.
- Stale takeover is rejected while old queued/running Jobs remain unreconciled.
- Resources are typed in configuration; GPU use is derived from resource kind,
  not a display-name allowlist.
- Projected and actual usage is monotonic and checked against Campaign, daily
  local GPU, backend, paid-compute, and physical-capacity limits.
- A runtime boundary creates a structured cancellation request. It never claims
  the process stopped.
- Cancelling a running Job requires external stop confirmation and an auditable
  reference. A running failure requires an observed exit code; stale-claim
  recovery requires external stop evidence for any running Job.
- Paid compute requires a reviewed code-registered control adapter with enforced
  cancellation and provider-side cost metering. Configuration declarations alone
  are insufficient.
- Every backend declares `paid = true` or `false`; paid backends require a
  positive planned cost, preventing a zero-cost declaration from skipping the
  paid-compute gate.

## Consequences

Goal Mode launch, state mutation, and GPU use become authorized transitions rather
than prompt conventions. Stale ownership is fenced. Misreported decreasing usage
is rejected. Operators must explicitly reconcile abandoned Jobs before takeover.

The current release does not ship a paid-provider control adapter, so paid compute
fails closed even when enabled in TOML. The repository remains single-host and
dependency-light; distributed locking and provider-specific schedulers are future
work.
