# Architecture

## Design goal

Codex Research Harness turns a vague mission into a persistent research process
that survives session compaction, agent restarts, and model changes. It is not a
monolithic autonomous-agent prompt. The harness separates strategy, execution,
state, evidence, communication, and human comprehension.

## Components

```text
Human observer-owner
        ↕
Codex App Research Director
        │
        ▼
Research Planner session
broad evidence + EDA + domain landscape + strategy
        │ Campaign Contract
        ▼
Fresh GPT-5.6 Sol High /goal session
one deep bounded Research Executor Campaign
        │ Handoff + evidence references
        ▼
Research Planner replans
```

The `researchctl loop` state machine derives every role transition from durable
ResearchPlan and Campaign files. It does not launch an AI process by itself; it
produces the deterministic next instruction for the Codex App Director or a
scheduled control task.

### Durable state

The repository owns Mission, strategy memory, Campaign Contracts, current state,
experiment registry, consultation artifacts, and Handoffs. GitHub Project owns
human-visible work status. Runtime process state and browser sessions stay local.

### Communication

agmsg is a thin notification/consultation transport among long-lived local
sessions. It does not own task lifecycle or scientific state. ChatGPT, Claude,
and Grok receive bounded Question Packs and return saved response artifacts.

### Human comprehension

The Director reads durable state and produces a short brief and deterministic
visuals. Human explanation depth never changes research quality or evidence
standards.

## Context ownership

| Layer | Contents | Lifetime |
|---|---|---|
| Constitution | AGENTS.md and invariant policy | repository |
| Role Skill | Planner or Executor workflow | task/session |
| Context Pack | current minimum evidence | campaign/plan |
| Durable memory | verified strategic findings/decisions | strategy epoch |
| Archive | logs, models, full responses, raw evidence | retained/searchable |

A fresh Executor never inherits a previous Executor conversation. A Planner
receives Handoffs, not transcripts. Advisors receive Question Packs. Before each
transition, `researchctl loop checkpoint` stores the derived action under ignored
local runtime state and renders `runtime/next-research-action.md`.

## Failure behavior

- optional advisor unavailable: continue with available agents/evidence
- browser/login expired: pause ChatGPT consultation only
- Executor stops: restart from Contract, state, commit, registry, and artifacts
- GitHub Project unavailable: local durable state continues; sync later
- hard budget reached: finish Handoff as budget exhausted and replan
- invalid evaluation/leakage: mark evidence invalid; never promote it
