# Planner–Executor research loop

## Planner epoch

A Planner epoch normally spans several Campaigns. Planner starts broad, maintains
a strategy portfolio, and issues one bounded campaign at a time. After roughly
3–5 Campaigns, a major premise change, or repeated compaction, create a fresh
Planner context from durable files to reduce anchoring.

## Campaign lifecycle

```text
Draft Contract → Validate → Ready → Goal execution → Checkpoints
→ Confirm/withdraw → Handoff → Planner synthesis
```

## Time gates

- 25% budget: valid measurement and calibrated ETA
- 50%: evidence must move a decision; otherwise narrow or withdraw
- 80%: no new branches; confirmation, synthesis, or withdrawal
- hard stop: complete a Handoff regardless of outcome

## Research progress

Progress means one of:

- important uncertainty reduced
- reproducible improvement
- plausible direction rejected with evidence
- strategy-changing anomaly
- measured capability that repays its cost

Code volume, GPU occupancy, or lengthy thought alone are not progress.


## Durable transition control

The Director must not infer the next role from conversation memory. Run:

```powershell
researchctl loop status
researchctl loop checkpoint
researchctl loop instruction
```

The state machine returns one of:

- `start_planner` — no durable ResearchPlan exists
- `run_planner` — the plan or selected Campaign Contract is incomplete
- `start_executor` — a ready Campaign has its bounded Context Pack and Goal prompt
- `monitor_executor` — a Campaign is active
- `resume_planner` — a Campaign finished with a validated Handoff
- `mission_complete` — the latest ResearchPlan is complete
- `repair_state` — durable files are missing or contradictory

The command deliberately does not start a model session. Codex App remains the
Director and executes the rendered instruction using the configured model and
Skill. This keeps orchestration inspectable and avoids hiding scientific state in
a daemon or chat transcript.
