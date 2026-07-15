# Evaluation contract

Not initialized. For Kaggle, Research Planner must define:

- official metric implementation and direction
- fixed folds or holdout data with row/group/time constraints
- seed policy
- preprocessing fit boundary
- OOF and test-prediction row-order contract
- leakage checks
- comparison uncertainty and promotion rules
- sealed confirmation policy where feasible

Executors use this contract; they do not silently change it.
