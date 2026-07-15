# Codex Research Harness — repository instructions

This repository is a **research operating harness**, not a normal application.
Its invariant is the autonomous loop:

`vague human mission → Research Planner → bounded Campaign Contract → GPT-5.6 Sol High /goal Research Executor → evidence handoff → Research Planner`

## First action in every new repository

1. Read `BOOTSTRAP.md`.
2. Run `researchctl doctor --profile quick` before changing setup state.
3. If `.research-lab/local/instance.json` is absent, invoke the
   `research-bootstrap` skill. Never improvise a parallel bootstrap path.
4. If setup is incomplete, resume it idempotently. Do not duplicate GitHub
   Projects, issues, ChatGPT Projects, or agent identities.

## Sources of truth

- Original human intent: `research/USER_INTENT.md`
- Mission: `research/MISSION.md`
- Current strategy: `research/strategy/CURRENT.md`
- Durable strategic memory: `research/strategy/MEMORY.md`
- Campaign contract/state/evidence: `research/campaigns/<ID>/`
- Experiment registry: `experiments/index.jsonl`
- Human-facing current status: `research/CURRENT_BRIEF.md`
- Local credentials, browser state, process IDs: `.research-lab/local/` and
  `runtime/` (never commit)
- Work state visible to humans: GitHub Project
- Code/evidence review: GitHub Pull Requests
- Cross-agent notifications: agmsg; it is never the state database

## Role boundaries

### Research Director

Talks with the human, reads the control plane, reports whether the lab is
healthy, and starts/resumes Planner or Executor sessions. It does not make
routine code edits or ingest raw logs into the human conversation.

### Research Planner

Uses the `research-planner` skill in an isolated session. It must inspect the
problem broadly: rules, evaluation, data-generating process, EDA, baseline,
domain knowledge, adjacent fields, historical/negative results, community
signals, current constraints, and prior campaign evidence. It may run bounded
analysis but does not own long GPU campaigns. It issues one measurable Campaign
Contract with success, withdrawal, time, GPU, cost, and fixed-evaluation terms.

### Research Executor

Uses the `research-executor` skill in a fresh GPT-5.6 Sol High `/goal` session,
one session per Campaign. It owns hypotheses, implementation, experiment
ordering, analysis, and bounded consultation. It may not silently alter the
mission, evaluation contract, resource budget, or campaign boundary.

## Research quality rules

- Evidence, not activity, is progress.
- A deep dive must name the decision it can change, the cheapest discriminating
  test, and a stop condition.
- Do not start expensive work without a valid Campaign Contract.
- Do not claim completion without reproducible artifacts and verification.
- Record valid negative results; they are research evidence.
- Preserve fixed CV/evaluation contracts unless the Planner opens a dedicated
  strategy campaign to change them.
- Research Planner must avoid strategy monoculture. It must consider data,
  domain, evaluation, cross-domain, opposing, and high-upside directions before
  convergence.
- The Executor recommends strategy; only the Planner selects the next Campaign.
- Context must be role-bounded. Never paste whole transcripts or raw logs into
  another agent when a Context Pack or Question Pack is sufficient.

## Human communication

The human is the observer-owner, not a scientific approval gate. Read
`research/setup/HUMAN_PROFILE.md` before human-facing updates and use
`lab-status`.

A normal update should make these five things obvious without technical detail:

1. What is running now?
2. Is evidence strengthening or weakening a winning path?
3. How much wall time, GPU time, and cost have been used?
4. What happens next?
5. Is the harness healthy, or is there an external boundary such as login or a
   hard budget limit?

Do not pause routine research to ask the human for scientific decisions.

## ChatGPT research partner

Use `chatgpt-research-partner`. During init, the human chooses either the Codex
built-in browser or Chrome with the official Codex Chrome extension installed from Plugins. Create one
ChatGPT Project for the research repository, store its URL only in local state,
and verify the exact configured Pro model label before every critical
consultation. Never silently fall back to a weaker model. Use new chats for new
questions and the saved conversation URL for genuine follow-ups.

## Security and external boundaries

- Never print, commit, paste into Issues/PRs, or store credentials in research
  files.
- Login, MFA, terms acceptance, new paid providers, hard-budget increases,
  public release, destructive external actions, and any legally required
  acknowledgement are external actions. Pause only the affected capability.
- Missing optional advisors must degrade gracefully; continue with available
  evidence and agents.
- Kaggle submissions follow the configured submission policy and competition
  rules. Setup tests are read-only and must never submit accidentally.

## Validation before committing

Run:

```powershell
python -m unittest discover -s tests -v
researchctl self-test
researchctl doctor --profile quick
```

On changes to schemas, skills, or the control plane, update tests and the
relevant ADR/documentation.
