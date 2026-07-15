# Kaggle research profile

The Kaggle profile is the first reference implementation, while the core harness
remains reusable for other research.

## Planner responsibilities

- official rules, deadline, metric, submission mode, external-data policy
- safe Kaggle CLI access and competition participation
- data inventory, train/test shift, group/time structure, leakage candidates
- baseline and fixed CV/evaluation contract
- public/private leaderboard risk
- prior competitions, public notebooks, Discussions, papers, domain knowledge
- compute/runtime fit

## Executor responsibilities

- one campaign-specific hypothesis family
- Smoke/Quick/Full/Confirm progression
- OOF and test predictions with row IDs/folds
- reproducible config/commit/artifacts
- leakage/reproduction audit

## Submission

Setup never submits. Submission behavior is a separate policy. Competition rules
and daily limits are authoritative. Public leaderboard movement is diagnostic,
not sufficient evidence for promotion.
