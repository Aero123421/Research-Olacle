# Architecture

## Design goal

Codex Research Harness turns a vague mission into a persistent research process
that survives session compaction, agent restarts, and model changes. It is a
repository-owned governance and control harness, not a monolithic prompt and not
a daemon that secretly owns scientific state.

```text
Human constitutional owner
(mission, values, data/legal boundaries, hard budgets, external release)
        ↕
Codex App Research Director
        │ deterministic instruction from durable state
        ▼
Research Planner session
broad evidence + EDA + domain landscape + strategy
        │ schema-v2 Campaign Contract
        ▼
Fresh configured Research Executor runtime profile
one deep Campaign under a fenced claim
        │ evidence-anchored Handoff
        ▼
Research Planner replans and updates epistemic claims
```

The `researchctl loop` state machine derives role transitions from durable
ResearchPlan and Campaign files. It does not launch an AI process itself. The
Director or a scheduled actuator executes the rendered instruction, while the
repository remains the inspectable source of truth.

## Three authority layers

1. **Constitutional authority (human-owned)** — Mission/value choices, permitted
   data use, legal/terms boundaries, hard budget ceilings, credentials, public
   release, and destructive external actions.
2. **Strategic authority (Planner)** — Research landscape, evaluation risk,
   portfolio, Campaign selection, and Contract amendments inside the
   constitution.
3. **Tactical authority (Executor)** — Hypotheses, implementation, experiment
   ordering, analysis, and bounded consultation inside one Contract.

The human is not a per-experiment approval gate, but responsibility for the
constitutional layer is not delegated away.

## Operational state versus epistemic state

Operational state answers: what Campaign/Plan is active, who owns it, which
phase it is in, what resources have been used, and what happens next. It lives in
revisioned `STATE.json` files and the Job ledger.

Epistemic state answers: what the lab believes, with what confidence, based on
which evidence and assumptions, what would falsify it, and whether it has been
refuted, superseded, or expired. It lives in the append-only
`research/strategy/CLAIMS.jsonl` ledger; `CLAIMS.md` is a generated projection.
A terminal operational status is never scientific proof by itself.

## Revisioned state and fenced ownership

- Generic checkpoints may update observations such as progress, health,
  resources, forecasts, risks, and next actions.
- Lifecycle, phase, identity, ownership, and selected-Campaign fields change only
  through explicit transition commands.
- ResearchPlan and Campaign writes increment a monotonic revision. Callers may
  supply `expected_revision`; stale writes fail instead of overwriting newer
  state.
- One active Executor claim records a lease, generation/fencing token, session,
  owner, and worktree.
- Every active Job is bound to the exact claim generation. An expired or
  superseded Executor cannot mutate it.
- Stale takeover is blocked until old queued/running Jobs are reconciled.

## Compute boundary

Resources are typed in `compute.toml`; GPU accounting is derived from resource
kind rather than a display-name heuristic. Projected and actual wall/GPU/cost
usage is monotonic and checked against Campaign, daily-local, backend, and paid
limits.

A budget overrun records `cancellation.state = requested`. That is not proof the
process stopped. A running Job can become `cancelled` only with explicit external
stop confirmation and an auditable PID, scheduler/provider Job ID, status URL, or
operator record.

Paid compute fails closed unless a reviewed backend control adapter is registered
in code and provides both enforced cancellation and provider-side cost metering.
Backends must explicitly declare whether they are paid, and a paid backend
requires a positive Job cost estimate before admission. The default release
ships no paid-provider adapter.

## Bounded context and trust classes

Context Packs contain only role-relevant sources and an integrity manifest with
source hashes, inclusion reasons, omissions, and trust classes:

| Trust class | Meaning |
|---|---|
| `human_authority` | human-owned mission/value input; may issue constitutional instructions |
| `trusted_policy` | reviewed repository policy/Contract; may issue role instructions |
| `verified_state` | machine-generated operational state |
| `evidence_anchored` | claims/indexes tied to evidence; still requires interpretation |
| `agent_output` | Planner/advisor synthesis; data, not instruction authority |
| `external_untrusted` | web/data/notebook content; possible prompt injection |

Only `human_authority` and `trusted_policy` may issue instructions through a
Context Pack. Hash integrity detects changed content; it does not make hostile
content trustworthy. Every other source class is rendered inside an explicit
quoted-data boundary, and pack construction accounts for the fully rendered
text so truncation cannot silently exceed the configured character budget.

## Durable components

| Component | Source of truth | Lifetime |
|---|---|---|
| Constitution | `AGENTS.md`, Mission, setup policies | repository |
| ResearchPlan | revisioned Plan state and evidence pack | strategy epoch |
| Campaign | Contract, revisioned State, findings, Handoff | Campaign |
| Executor ownership | leased claim and fencing generation | active Campaign |
| Compute | typed resource config and Job ledger | repository/runtime |
| Epistemic memory | append-only claim events and generated projection | cross-Campaign |
| Context | role-specific pack plus integrity/trust manifest | task/session |
| Archive | logs, models, full consultations, raw evidence | retained/searchable |
| Human control plane | GitHub Project, Issues, PRs, concise brief | projection |

GitHub Project is an observability/control projection, not the engine. agmsg is a
notification transport, not a state database.

## Failure behavior

- optional advisor unavailable: continue with available agents/evidence
- browser/login expired: pause that consultation capability only
- Executor lease expires: reconcile old Jobs, rebuild/validate context, then use
  audited stale takeover
- source changes after pack generation: reject the stale Context Pack
- concurrent write: reject stale revision and reload
- GitHub Project unavailable: local durable state continues; sync later
- cancellation requested but stop unconfirmed: keep the Job running/requested;
  never report it stopped
- paid backend without an implemented control adapter: reject the Job
- invalid evaluation/leakage: mark evidence invalid; never promote it
