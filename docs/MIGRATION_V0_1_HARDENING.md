# Migration: revisioned/fenced research state hardening

This change is intentionally strict. It closes paths that could bypass Campaign
ownership, lifecycle, budget accounting, or evidence requirements.

## Compatibility

- Schema-v1 Campaign Contracts and Handoffs remain readable.
- New Campaign defaults use schema v2 and require epistemic safeguards before
  `finalize`.
- Legacy Contract owners with `runtime`, `model`, and `effort` remain valid.
  New Contracts should use `owner.runtime_profile`.
- Existing Plan/Campaign state without `revision` is treated as revision 0 and
  gains a revision on the next successful write.
- A queued legacy Job without claim binding can bind when first started by the
  current claim. An already-running unbound/stale Job must be audited and force
  reconciled as failed/cancelled; it cannot be adopted silently.

## CLI changes

Active Campaign operations require the current claim:

```powershell
$state = researchctl campaign claim-executor C-001 --session-id <SESSION> --worktree <PATH> | ConvertFrom-Json
$claimId = $state.executor.claim_id
$revision = $state.revision

researchctl campaign checkpoint C-001 --claim-id $claimId --expected-revision $revision --patch checkpoint.json
researchctl campaign transition C-001 --status validating --phase confirmation --claim-id $claimId --expected-revision <REVISION>
researchctl campaign complete C-001 --claim-id $claimId --expected-revision <REVISION> --handoff HANDOFF.json
```

Job start/heartbeat requires `--claim-id`; active registration should include it.
A running Job may be marked cancelled only with stop evidence. Marking a
running Job failed requires an observed process exit code; stale-claim recovery
requires external stop evidence for either failed or cancelled status:

```powershell
researchctl job finish JOB-123 --status cancelled --claim-id $claimId `
  --failure-summary "Budget boundary reached" `
  --external-stop-confirmed `
  --external-stop-reference "scheduler:job-123:STOPPED"
```

For an expired claim, first confirm/stop the external process, then use the
audited recovery path with `--force-stale-claim`. Stale takeover remains blocked
until old queued/running Jobs are terminal.

ResearchPlan lifecycle is explicit:

```powershell
researchctl plan checkpoint RP-001 --expected-revision <REVISION> --patch observations.json
researchctl plan transition RP-001 --status researching --expected-revision <REVISION>
researchctl plan link-campaign RP-001 C-001 --expected-revision <REVISION>
```

## Contract v2 additions

Ready v2 Contracts need:

- `counter_hypotheses`
- `metric_gaming_risks`
- `reversal_evidence`
- `adoption_exclusions`
- `amendment_policy.requires_replanning_for`
- `amendment_policy.record_location`

## Handoff v2 additions

Each evidence item needs `observation`, `inference`, and `confidence`, in addition
to claim/artifact/commit provenance. The Handoff also needs:

- `assumptions`
- `unresolved_questions`
- `unverified_leads`
- `decision_reversal_evidence`

## Epistemic claims

Use `researchctl claim-ledger` instead of silently replacing strategic belief
prose. `CLAIMS.jsonl` is append-only; `CLAIMS.md` is regenerated automatically.
Corroborated/refuted claims require evidence references. Use `supersedes` to
replace an old claim while retaining correction history.

## Paid compute

Paid compute now fails closed unless a provider backend has a reviewed
code-registered adapter that enforces cancellation and retrieves authoritative
provider cost. No such production adapter ships in this release. Keep
`paid_compute.enabled = false` until one is implemented and tested.

Each backend must now declare `paid = true` or `paid = false`. A Job targeting a
paid backend must provide a positive `planned_cost_jpy`; zero is no longer
accepted as a way to defer or bypass paid-compute authorization.
