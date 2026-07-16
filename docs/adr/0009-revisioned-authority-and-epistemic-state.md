# ADR-0009: Revisioned authority and append-only epistemic state

Status: accepted

## Context

A generic deep-merge checkpoint could change authoritative fields such as status,
phase, owner, or selected Campaign without following the intended lifecycle.
Long-running agents can also overwrite newer state, and durable prose can turn an
old interpretation into an unexamined permanent belief. Concrete model names in
Campaign state couple governance to one product version.

## Decision

1. ResearchPlan and Campaign state carry monotonic revisions. Callers may provide
   `expected_revision`; stale writes fail.
2. Generic checkpoints are limited to non-authoritative observations. Lifecycle,
   phase, selected Campaign, identity, and ownership change only through explicit
   transition functions.
3. Campaign ownership is expressed by a leased claim with a fencing generation;
   Jobs bind to that generation.
4. Campaign Contracts name a stable `runtime_profile`. Concrete runtime/model
   preferences are resolved in configuration and validated before activation.
   Legacy owner triples remain readable for migration.
5. Schema-v2 Contracts add counter-hypotheses, metric-gaming risks, reversal
   evidence, adoption exclusions, and an amendment policy.
6. Schema-v2 Handoffs distinguish observation from inference/confidence and retain
   assumptions, unresolved questions, unverified leads, and decision-reversal
   evidence.
7. Cross-Campaign beliefs live in an append-only epistemic claim ledger with
   evidence, assumptions, confidence, falsifier, expiry, refutation, and
   supersession. A generated Markdown file is a projection, not the primary log.
8. Context sources carry explicit trust classes and omission records.

## Consequences

State corruption and lost updates fail visibly instead of being silently merged.
Model upgrades no longer require changing the Campaign state machine. Strategy
memory can preserve uncertainty and correction history rather than only the
latest narrative.

Schema-v1 Contracts/Handoffs remain readable, but new defaults use v2. Existing
scripts that patch lifecycle fields or omit active `claim_id` values must migrate
to the explicit commands documented in
[`../MIGRATION_V0_1_HARDENING.md`](../MIGRATION_V0_1_HARDENING.md).
