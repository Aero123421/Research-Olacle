# Research Executor protocol

One Campaign is executed in one fresh session resolved from the Contract's
configured `research_executor` runtime profile. The Executor owns hypotheses,
implementation, experiment ordering, analysis, bounded consultation,
checkpoints, and reproducible evidence. It cannot alter Mission, evaluation
contract, hard budget, or global strategy.

Active operations are authorized by a renewable Executor claim. Checkpoints and
lifecycle transitions use optimistic `revision` checks; compute Jobs are bound
to the claim's fencing generation. An expired or superseded Executor cannot
continue writing.

The Executor distinguishes observations from inferences, records durable belief
changes in the append-only epistemic claim ledger, and returns assumptions,
unresolved questions, unverified leads, and decision-reversal evidence in the
Handoff. Cancellation requests are not treated as confirmed process stops.
