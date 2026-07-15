---
name: eda-diagnostics
description: Generate reproducible decision-oriented EDA and data-science diagnostics for Research Planner or a bounded Executor question. Use for data inventory, keys, missingness, duplicates, target structure, groups/time, train-test shift, leakage candidates, baseline/fold diagnostics, residuals, and runtime profile. Avoid decorative analysis that cannot change a research decision.
---

# EDA Diagnostics

## Principle

EDA exists to reduce a named uncertainty or choose a research direction. Before
analysis, write the decision it can change and the cheapest sufficient output.

## Minimum Planner EDA

- file/table roles and joins
- row/column counts and identifiers
- target distribution and missing labels
- missingness, duplicates, constants, high-cardinality columns
- time/group/entity structure
- train/test distribution differences
- target/metadata leakage candidates
- sample submission/order contract
- baseline fold scores and runtime when available

Use deterministic scripts and save data inventories under the current
ResearchPlan evidence directory. The base CLI supports CSV:

```powershell
researchctl eda profile path\to\train.csv --output research\plans\RP-001\evidence
```

For Parquet/Arrow and richer diagnostics, install the optional data extra and
keep scripts in the repository. Do not make a large notebook the only source of
truth.

## Output

- machine-readable metrics/profile
- concise Markdown interpretation
- charts generated from code
- leakage/shift hypotheses and cheapest tests
- explicit limitations
