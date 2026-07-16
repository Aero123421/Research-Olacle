---
name: research-loop
description: Operate the durable Research Planner ↔ configured Research Executor loop from repository state. Use in the Codex App Director or a scheduled control task to start/run Planner, start/monitor one fresh claimed Executor, resume Planner after Handoff, finish the mission, or repair contradictory state. Never use remembered chat as the state machine.
---

# Research loop orchestrator

Run:

```powershell
researchctl loop checkpoint
researchctl loop instruction
```

Then execute exactly the derived transition.

## Invariants

- The latest revisioned ResearchPlan and selected Campaign determine the next role.
- Planner and Executor use separate sessions and bounded Context Packs.
- A `ready` Campaign starts one fresh session resolved from its configured
  Research Executor runtime profile.
- Launch requires an atomic claim; active writes and Jobs require its exact
  `claim_id` and fencing generation.
- A stale claim may be taken over only after old queued/running Jobs are audited
  and reconciled as failed/cancelled.
- Lifecycle changes use explicit transition commands. Generic checkpoints cannot
  modify status, phase, identity, ownership, or revision.
- A completed Campaign has a validated evidence-anchored `HANDOFF.json` and no
  outstanding Jobs before Planner resumes.
- Planner resumes from Handoff, strategy memory, the epistemic claim ledger,
  Evidence Index, and resource state—not the Executor transcript.
- Missing, stale, or contradictory state triggers repair, never a guessed transition.
- Human-owned mission/value, data/legal, hard-budget, and external-action
  boundaries remain outside routine scientific autonomy.

The Director may use agmsg to notify a live Planner or Executor, but agmsg never
owns loop state or authorization.
