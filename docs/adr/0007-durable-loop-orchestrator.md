# ADR 0007: derive Planner/Executor transitions from durable state

## Status

Accepted.

## Decision

The Codex App Director uses `researchctl loop` and the `research-loop` Skill to derive the next action from the latest ResearchPlan, Campaign Contract, Campaign State, Context Pack, and Handoff. Conversation memory and agmsg notifications are not the state machine.

## Consequences

- A restart or context compaction can recover the loop without replaying chats.
- A ready Campaign starts one fresh session resolved from its Research Executor runtime profile only after an atomic, fenced Executor claim.
- A completed Campaign cannot return to Planner without a validated Handoff.
- UI automation remains a thin actuator; deterministic transition logic is tested in Python.
