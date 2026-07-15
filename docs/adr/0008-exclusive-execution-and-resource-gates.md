# ADR-0008: Exclusive Campaign execution and enforced resource boundaries

Status: accepted

## Context

Planner, Director monitoring, Goal Mode, and compute workers can operate in
parallel on the Windows research host. File existence and dashboard warnings are
not sufficient to prevent two Executors from owning one Campaign, two jobs from
using the same GPU, or a job from crossing a hard time/cost boundary.

## Decision

- Shared IDs and mutable ledgers use repository-local cross-platform locks.
- A ready Campaign must pass Context Pack integrity validation and complete an
  atomic `ready → executing` claim before `/goal` starts.
- The claim records its owner, session, worktree, heartbeat, and renewable lease.
- Compute jobs are authorized on registration and again on start against the
  Campaign, daily local GPU, paid-compute, backend, and physical-resource policy.
- Runtime heartbeats persist a hard-stop marker when measured usage crosses a
  boundary.
- Context Packs are paired with source-hash manifests; incomplete or stale packs
  are not runnable.

## Consequences

Goal Mode launch and GPU use become explicit state transitions rather than
conventions in prompts. A stale claim can be taken over deliberately after its
lease expires, while a second live claim is rejected. The repository remains
single-host and dependency-light; distributed locking and remote schedulers are
outside the current scope.
