# Context and memory management

Active context is bounded and role-specific. Durable memory is explicit state on
disk, not an assumption that a chat remains available forever.

## Trust-aware Context Packs

Every source receives a trust class and inclusion reason. Only
`human_authority` and `trusted_policy` content may issue instructions.
`verified_state`, `evidence_anchored`, `agent_output`, and `external_untrusted`
content is rendered inside explicit Markdown quote boundaries as data to
evaluate. This prevents a web page, notebook, advisor, prior agent, or generated
state record from becoming an instruction source merely because it was copied
into context. The rendered pack, including separators and any budget notice, is
rejected rather than written if it would exceed the configured character limit.

The manifest records source hashes, required/optional status, truncation,
included characters, omitted relevant sources, and role metadata. A source change
invalidates the pack. Hashes prove content identity, not truth or safety.

## Planner memory

- `research/strategy/MEMORY.md`: compact verified/reusable strategic findings
- `research/strategy/EVIDENCE_INDEX.md`: locations and provenance for detailed evidence
- `research/strategy/CLAIMS.jsonl`: append-only epistemic claim events
- `research/strategy/CLAIMS.md`: generated current-belief projection

A claim records statement, confidence, evidence references, assumptions,
falsifier, optional expiry, Campaign provenance, and refutation/supersession.
Operational state is intentionally separate.

## Campaign state

`STATE.json` is revisioned machine-readable operational state. `STATE.md` is its
generated view. `FINDINGS.md` contains confirmed Campaign-local findings;
`HYPOTHESES.md` contains tentative explanations and falsification tests. Raw logs
and artifacts stay outside active context and are linked by exact path/ID.

## Checkpoint before pause or compaction

- persist phase/action/resources/forecast with current `claim_id` and revision
- use an explicit transition for lifecycle/phase changes
- separate observations, inferences, assumptions, and unresolved questions
- register experiments and link raw evidence
- update the claim ledger only for cross-Campaign durable belief changes
- list the next three actions
- synchronize material GitHub status
- rebuild and validate the role Context Pack after source changes

A session can be discarded after this checkpoint without losing operational or
epistemic state. A checkpoint cannot be used to reduce resource totals, rewrite
experiment history, revive an expired claim, or silently alter the Contract.
