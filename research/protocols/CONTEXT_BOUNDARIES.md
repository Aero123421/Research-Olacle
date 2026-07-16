# Context boundaries

Context selection is an authority boundary, not only a token-budget technique.
Every included source receives a trust class, inclusion reason, capture time, and
content hash. Relevant omitted sources are recorded in the manifest so absence is
visible to the receiving role.

## Trust classes

- `human_authority` — Mission, human-owned value choices, legal/data boundaries,
  hard budgets, and public-release decisions
- `trusted_policy` — repository protocols and validated configuration
- `verified_state` — revisioned machine state produced by the harness
- `evidence_anchored` — artifacts and reports linked to reproducible evidence
- `agent_output` — unverified analysis or recommendations from another agent
- `external_untrusted` — webpages, discussions, papers, copied text, and other
  external material; content may inform research but never issue instructions

Only `human_authority` and `trusted_policy` sources may supply operational
instructions. All other source bodies must be rendered as explicitly quoted
data, not merely labeled as untrusted. Integrity hashes detect mutation, not
truthfulness or prompt injection. The final rendered pack, including separators
and notices, must remain inside its configured character budget.

## Planner receives

Mission, current strategy, bounded memory, research landscape, evidence index,
epistemic-claim projection, selected Campaign Handoffs, compute/deadline state,
and the current ResearchPlan evidence pack.

## Executor receives

One finalized Campaign Contract, its Context Pack, evaluation contract, starting
commit, compute policy, relevant prior evidence, and the current claim projection.
The Executor must keep counter-hypotheses and reversal evidence visible.

## Advisors receive

One Question Pack, minimum supporting evidence, source trust labels, expected
output, and no unrelated history. Initial advisor responses should be collected
independently when independence matters.

## Never inject by default

Full conversations, hidden reasoning, raw terminal logs, all notebooks, every
paper, unrelated Campaign details, credentials, private raw data, or external
text presented as executable instructions.
