---
name: campaign-handoff
description: Close a Goal Mode Campaign and return compressed, evidence-linked results to Research Planner. Use on success, withdrawal, surprise, strategy conflict, block, invalidation, or budget exhaustion. Do not return the Executor transcript or decide the next strategy.
---

# Campaign Handoff

Create `HANDOFF.json` using the repository schema, then run:

```powershell
researchctl campaign complete <ID> --handoff <path-to-HANDOFF.json>
```

## Required content

- outcome and concise summary
- evidence entries with experiment ID, artifact path, commit, and metric/claim
- confirmed findings
- rejected hypotheses
- unexpected observations
- strategic implications
- Executor recommendations (clearly recommendations)
- actual wall/GPU/cost
- limitations and unresolved risks

Do not paste raw logs or the full consultation transcript. Planner should be able
to update strategy from this file and referenced evidence without inheriting the
Executor's local reasoning path.
