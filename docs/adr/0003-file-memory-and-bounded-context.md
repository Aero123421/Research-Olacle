# ADR-0003: File memory and bounded role context

Status: accepted

## Context

Long research must survive compaction and restart, but loading all history into
every model causes context pollution.

## Decision

Use explicit Markdown/JSON memory, current state, Context Packs, and archives.
Planner, Executor, and advisors receive different bounded views. Checkpoints
flush durable facts before pause or compaction.

## Consequences

Agents must maintain files carefully. Memory is inspectable and portable; hidden
chat continuity is not a dependency.
