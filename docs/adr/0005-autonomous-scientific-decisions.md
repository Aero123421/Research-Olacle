# ADR-0005: Human is observer-owner, not scientific approval gate

Status: accepted

## Context

The system is intended to self-drive. Requiring human approval for ordinary
hypothesis selection or campaign continuation would stop the research loop and
force a non-researcher to make technical judgments.

## Decision

Planner and Executor make scientific decisions autonomously under explicit
mission, evaluation, time, compute, cost, and rule constraints. Human interaction
focuses on observability and external actions that AI cannot cross.

## Consequences

The harness needs stronger evidence, withdrawal, audit, and budget contracts.
Human-facing communication optimizes understanding, not approval collection.
