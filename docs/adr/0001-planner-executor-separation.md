# ADR-0001: Separate Research Planner and Goal Mode Executor

Status: accepted

## Context

Broad strategy and deep implementation create different context needs and
failure modes. A single long session tends to anchor on its first approach and
pollute strategic context with local logs and implementation details.

## Decision

Research Planner and Research Executor use separate sessions and separate Context
Packs. Planner expands and selects. One fresh session resolved from the configured
Research Executor runtime profile pursues one Campaign. Only an evidence-anchored
Handoff returns to Planner.

## Consequences

Research state must live on disk. Handoff schemas and context builders are core
infrastructure. Some conversational continuity is intentionally discarded to
reduce anchoring and context rot.
