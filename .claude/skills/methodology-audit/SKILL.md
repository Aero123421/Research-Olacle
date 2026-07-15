---
name: methodology-audit
description: Audit a minimum-necessary research Question Pack for evaluation validity, leakage, confounding, statistics, reproducibility, falsification, and evidence quality. Use in the methodology-auditor subagent; do not edit the research repository.
---

# Methodology audit

1. Read `research/protocols/EVIDENCE_STANDARD.md`,
   `research/protocols/EVALUATION_CONTRACT.md`, and the supplied Question Pack.
2. Separate observations, inferences, assumptions, and external claims.
3. Inspect only the referenced code, metrics, folds, artifacts, and commits.
4. Test for leakage, target contamination, split mismatch, metric mistakes,
   multiplicity, seed/fold fragility, implementation asymmetry, and non-reproducible
   manual state.
5. Name the strongest alternative explanation and the cheapest discriminating
   experiment.
6. Return a structured report. Do not write to the repository; the caller records
   the answer and provenance.
