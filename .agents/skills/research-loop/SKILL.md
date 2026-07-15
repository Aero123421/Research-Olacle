---
name: research-loop
description: Operate the durable Research Planner ↔ GPT-5.6 Sol High /goal Research Executor loop from repository state. Use in the Codex App Director or scheduled control task to decide whether to start/run Planner, start/monitor one fresh Executor, resume Planner after Handoff, finish the mission, or repair state. Never use remembered chat as the state machine.
---

# Research loop orchestrator

Run:

```powershell
researchctl loop checkpoint
researchctl loop instruction
```

Then execute exactly the derived transition.

## Invariants

- The latest ResearchPlan and selected Campaign state determine the next role.
- Planner and Executor use separate sessions and bounded Context Packs.
- A Campaign in `ready` state starts one fresh GPT-5.6 Sol High `/goal` session.
- An active Campaign is observed through durable checkpoints; routine status checks must not interrupt it.
- A completed Campaign must have a validated `HANDOFF.json` before Planner resumes.
- Planner resumes from Handoff, strategy memory, Evidence Index, and resource state—not the Executor transcript.
- Missing or contradictory state triggers repair, never a guessed transition.
- Scientific transitions are autonomous. External login, terms, or hard-budget boundaries pause only the affected capability.

The Director may use agmsg to notify a live Planner or Executor, but agmsg never owns the loop state.
