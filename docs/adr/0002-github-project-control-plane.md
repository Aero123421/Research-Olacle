# ADR-0002: GitHub Project is the human control plane

Status: accepted

## Context

The human needs time, GPU, ownership, evidence, and next actions without reading
agent transcripts or raw logs.

## Decision

GitHub Project owns human-visible work status. Pull Requests own plans, code,
and evidence review. Repository files own scientific state. GitHub Project is
created from a repository-owned spec, with browser-completed saved views.

## Consequences

The harness remains self-contained and cloneable. Project sync is event-driven.
GitHub outages do not erase local research state.
