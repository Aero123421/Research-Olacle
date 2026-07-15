# Context and memory management

This design borrows two useful distinctions from durable agent harnesses:

1. active context is bounded and task-specific
2. memory is explicit state written to disk, not an assumption that a chat will
   remain available forever

## Planner memory

`research/strategy/MEMORY.md` contains verified and reusable facts only. It has a
strict size budget. Detailed evidence is linked through `EVIDENCE_INDEX.md`.

## Campaign state

`STATE.json` is machine-readable current state. `FINDINGS.md` contains confirmed
findings. `HYPOTHESES.md` contains tentative claims and falsification tests.
Raw logs and artifacts are excluded from active context.

## Checkpoint before compaction

Before pause or compaction:

- persist phase/action/resources/forecast
- separate confirmed findings from hypotheses
- register experiments
- link raw evidence
- list the next three actions
- synchronize material GitHub status

A session can be discarded after this checkpoint without losing research state.
