# Evidence standard

A research claim is promotable only when linked to reproducible code/config,
commit, evaluation contract, metric/fold details, resource use, artifacts, and
important limitations. Advisor opinions and leaderboard movement are hypotheses
or diagnostics, not proof by themselves.

Every evidence-bearing Handoff entry separates:

- **observation** — what was measured or directly seen
- **inference** — what the observation suggests
- **confidence** — low, medium, or high
- **provenance** — experiment ID, artifact path, and commit

Durable claims belong in `research/strategy/CLAIMS.jsonl`, not only prose. Each
claim records confidence, assumptions, evidence references, a falsifier, optional
expiry, and whether it is tentative, corroborated, refuted, or superseded.
Operational status such as `completed` is never evidence by itself.
