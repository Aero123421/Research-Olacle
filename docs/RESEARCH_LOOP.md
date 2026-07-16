# Planner–Executor research loop

## Planner epoch

A Planner epoch normally spans several Campaigns. Planner starts broad, maintains
a strategy portfolio, and issues one bounded Campaign at a time. After roughly
3–5 Campaigns, a major premise change, repeated compaction, or repeated selection
from one narrow method family, create a fresh Planner context and perform a blind
strategy audit from durable evidence.

## ResearchPlan lifecycle

ResearchPlan state is revisioned and lifecycle changes are explicit:

```text
draft → researching → ready → campaign_running → replanning → ... → complete
```

Not every edge is legal. Use `researchctl plan transition` or
`researchctl plan link-campaign`; generic Plan checkpoints cannot modify status,
strategy epoch, selected Campaign, identity, or revision. Supplying
`--expected-revision` prevents lost updates.

## Campaign lifecycle

```text
Draft Contract → Validate/finalize → Ready → Activate → Claim Executor
→ Execute/Wait/Validate/Report → Reconcile Jobs → Handoff → Complete
→ Planner synthesis
```

Campaign checkpoints cannot patch lifecycle, phase, identity, or Executor fields.
Use `researchctl campaign transition` with the current claim and expected
revision. Completion requires the same live claim, a schema-valid Handoff,
existing evidence artifacts, no queued/running Jobs, and resource totals no lower
than durable accounting.

## Contract epistemic safeguards

A schema-v2 ready Contract includes not only success/withdrawal and budget, but
also:

- credible counter-hypotheses
- ways the metric/proxy can be gamed or misread
- evidence that should reverse the decision
- conditions where nominal success must not be adopted
- an amendment policy for goal, evaluation, budget, or fixed constraints

Contract amendments that cross those boundaries require Planner replanning; the
Executor cannot silently redefine success.

## Executor claim and fencing

Before launch:

```powershell
researchctl context executor C-001
$claim = researchctl campaign claim-executor C-001 --session-id <SESSION> --worktree <PATH> | ConvertFrom-Json
$claimId = $claim.executor.claim_id
```

The claim has a renewable lease and a monotonic generation/fencing token. Every
active checkpoint, transition, Job start/heartbeat/finish, and completion must
present the exact current `claim_id`. A stale generation cannot continue writing.
Stale takeover is blocked until old queued/running Jobs are audited and reconciled
as failed or cancelled.

## Time gates

- 25% budget: valid measurement and calibrated ETA
- 50%: evidence must move a decision; otherwise narrow or withdraw
- 80%: no new branches; confirmation, synthesis, or withdrawal
- budget exhausted: request cancellation, confirm actual stop, account resources,
  then produce a Handoff regardless of outcome

A cancellation request is not a stop. The Job remains running/requested until an
external process/provider stop is confirmed with an auditable reference.

## Epistemic loop

Research progress means important uncertainty reduced, reproducible improvement,
a plausible direction rejected with evidence, a strategy-changing anomaly, or a
measured capability that repays its cost. Code volume and GPU occupancy are not
progress by themselves.

Planner and Executor use `researchctl claim-ledger` for durable beliefs. Claims
carry evidence, assumptions, confidence, falsifiers, optional expiry, and status.
Refutation and supersession append new events; old belief history is not rewritten.
Handoffs separate observation from inference and preserve unresolved questions,
unverified leads, and evidence that could reverse the recommendation.

## Durable transition control

The Director must not infer the next role from conversation memory:

```powershell
researchctl loop status
researchctl loop checkpoint
researchctl loop instruction
```

The state machine returns one of:

- `start_planner` — no durable ResearchPlan exists
- `run_planner` — Plan or selected Contract is incomplete
- `start_executor` — ready Campaign has a hash-verified Context Pack and can be claimed
- `monitor_executor` — Campaign has one live Executor claim/lease
- `resume_planner` — Campaign completed with a validated Handoff
- `mission_complete` — latest ResearchPlan is complete
- `repair_state` — files, lease, context, or transitions are contradictory

The command deliberately does not launch a model session. The Director executes
the deterministic instruction using the runtime profile resolved from
configuration, keeping orchestration inspectable rather than hidden in a daemon.
