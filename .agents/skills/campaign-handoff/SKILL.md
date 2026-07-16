---
name: campaign-handoff
description: Close a claimed Campaign and return compressed, evidence-anchored results to Research Planner. Use on success, withdrawal, surprise, strategy conflict, block, invalidation, or budget exhaustion. Do not return the Executor transcript or choose the next strategy.
---

# Campaign Handoff

Create a schema-v2 `HANDOFF.json`, reconcile every queued/running Job, then run:

```powershell
researchctl campaign complete <ID> `
  --claim-id <CLAIM_ID> `
  --expected-revision <REVISION> `
  --handoff <path-to-HANDOFF.json>
```

Only the current, unexpired Executor claim may complete a Campaign. Completion
fails when a Job is still queued or running, an evidence artifact is missing, or
`resources_actual` is lower than durable Campaign/Job accounting.

## Required content

- outcome and concise summary
- evidence entries that separate `observation` from `inference`, declare
  confidence, and cite experiment ID, artifact path, and commit
- confirmed findings and rejected hypotheses
- unexpected observations and strategic implications
- Executor recommendations, clearly marked as recommendations
- actual wall/GPU/cost usage
- limitations and assumptions
- unresolved questions and unverified leads/anomalies
- evidence that should reverse the recommendation

Do not paste raw logs or the full consultation transcript. Planner must be able
to update the claim ledger and strategy from this file and its referenced
evidence without inheriting the Executor's private reasoning path.
