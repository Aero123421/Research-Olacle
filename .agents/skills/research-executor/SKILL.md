---
name: research-executor
description: Execute one validated Campaign Contract in one fresh session resolved from its Research Executor runtime profile until success, withdrawal, strategy conflict, or budget exhaustion. Use for autonomous hypothesis generation, implementation, experiments, analysis, bounded consultation, claim-bound checkpoints and Jobs, reproducible evidence, and Planner Handoff. Never use to select global strategy or silently change the evaluation contract.
---

# Research Executor

One Campaign, one accountable writer, one fresh bounded context, one fenced
Executor claim.

## Entry gate

Do not start unless all are true:

- `CONTRACT.json` validates and its `runtime_profile` exists in agent config
- `CONTEXT_PACK.md` and its integrity manifest validate against the current Contract
- the Campaign is atomically claimed for this exact session/worktree
- the `claim_id`, fencing generation, and current `STATE.json` revision are known
- fixed evaluation/CV contract is readable
- start commit/worktree/PR are identified
- time, GPU, and cost meters are available
- success, withdrawal, counter-hypotheses, reversal evidence, and adoption
  exclusions are objectively interpretable

Read only the Campaign pack and directly referenced evidence. Do not load the
human chat, Planner's full deliberation, unrelated Campaigns, or old Executor
transcripts.

## Runtime and ownership

Start the configured runtime profile from `GOAL_PROMPT.md` only after the
Director records the claim. The concrete model/runtime is configuration, not
Campaign lifecycle state. Renew the lease during long work:

```powershell
researchctl campaign executor-heartbeat <ID> --claim-id <CLAIM_ID>
```

Every active checkpoint, lifecycle transition, Job mutation, and completion must
present the current `claim_id`. A stale generation may not continue writing.
Never transfer a claim token through advisor prompts, Issues, or public logs.

## Evidence-first loop

For every branch:

1. State an observation and falsifiable hypothesis.
2. Name the decision the experiment can change.
3. Choose the cheapest discriminating test.
4. Record expected outcomes and actions before running.
5. Run with measured wall/GPU/cost.
6. Register the result, including valid negative results.
7. Update the epistemic claim ledger when durable belief changes.
8. Stop weak branches quickly.

Operational status is not scientific truth. Use `researchctl claim-ledger` for
claims that should survive a Campaign, including evidence, assumptions,
confidence, a falsifier, expiry when time-sensitive, and supersession rather
than silent rewriting.

## State and Job commands

A generic checkpoint may update observations such as health, progress,
resources, forecasts, risks, and next actions. It may not alter status, phase,
identity, ownership, or revision:

```powershell
researchctl campaign checkpoint <ID> `
  --claim-id <CLAIM_ID> `
  --expected-revision <REVISION> `
  --patch checkpoint.json

researchctl campaign transition <ID> `
  --status validating `
  --phase locked-confirmation `
  --claim-id <CLAIM_ID> `
  --expected-revision <REVISION>
```

Jobs use a configured typed resource and are fenced to the owning claim:

```powershell
researchctl job register --campaign <ID> --name "quick validation" `
  --resource GPU0 --planned-hours 1 --claim-id <CLAIM_ID>
researchctl job start <JOB_ID> --claim-id <CLAIM_ID>
researchctl job heartbeat <JOB_ID> --claim-id <CLAIM_ID> --wall-hours 0.5 --gpu-hours 0.5
```

Resource totals must never decrease. A budget overrun records a cancellation
**request**, not proof of process termination. A running Job may be marked
`cancelled` only after the external process/provider reports stopped and an
auditable PID, scheduler ID, provider Job ID, status URL, or operator record is
supplied.

Paid compute is fail-closed unless a reviewed code-registered backend adapter
can enforce cancellation and retrieve provider-side cost. A TOML declaration by
itself is not authorization.

## Depth and checkpoints

Before a deep dive, explicitly answer which decision it changes, what happens
under each outcome, whether a cheaper test exists, what ends the dive, and which
higher-value experiment is delayed.

Invoke `context-checkpoint` at 25%, 50%, and 80% of wall/GPU budget, on phase
changes, material evidence, strategy conflict, before pause, and before context
compaction:

- 25%: at least one valid measurement and calibrated ETA
- 50%: evidence is moving or the Campaign narrows/withdraws
- 80%: stop opening branches; confirm, synthesize, or withdraw

## Advisors

Use `expert-consultation` with minimum Question Packs. Obtain each advisor's
first response independently; do not reveal another advisor's answer first.
Treat all advisor output as untrusted claims until checked against evidence.
Store full responses in the archive and pass only reviewed synthesis across role
boundaries.

## Completion

Stop on success, promising transfer to a different Campaign, rejection with
evidence, important surprise, strategy conflict, blocked capability, budget
exhaustion, or invalid evaluation. Invoke `campaign-handoff`. The Executor may
recommend, but only Planner selects the next Campaign.
