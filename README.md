# Codex Research Harness

**Turn a vague human objective into an observable, autonomous research loop powered by Codex Goal Mode.**

Codex Research Harness is a Windows-first, GitHub-native repository template for
running long-horizon research with a strict separation between broad research
planning and deep campaign execution:

```text
human mission
   ↓
Research Planner
(rules + EDA + domain landscape + advisors + strategy)
   ↓
Campaign Contract
(goal + evidence criteria + withdrawal + time/GPU/cost budget)
   ↓
configured Research Executor runtime profile
(hypotheses + implementation + experiments + analysis)
   ↓
evidence-anchored Handoff
(observations + inferences + uncertainty + artifact references)
   ↓
Research Planner replans
```

The human owns the mission, value choices, data/legal boundaries, hard budgets,
and external release decisions, but is not a routine per-experiment approval gate.
GitHub Projects and Pull Requests make it easy to see what is running, what
evidence has changed, how much wall/GPU time has been used, and what happens
next—without having to follow implementation details.

[日本語 README](README.ja.md)

## What is included

- **Research Planner preset** for broad domain research, competition/rule
  analysis, reproducible EDA, baseline diagnostics, cross-domain search,
  strategy portfolios, and bounded advisor consultation.
- **Research Executor runtime profile** for one fresh bounded session per
  Campaign, with the concrete runtime/model resolved from configuration.
- **Durable loop orchestrator** that derives the next Planner/Executor transition
  from repository state, never from remembered chat.
- **Revisioned state machines and fenced ownership**: lifecycle changes use
  explicit commands, active writes require the current Executor claim, stale
  revisions fail, and Jobs are bound to the owning claim generation.
- **Typed compute resources and auditable cancellation**: unknown resource
  names fail closed, GPU accounting follows resource kind, and a stop request is
  never reported as a confirmed external stop without an audit reference.
- **Epistemic claim ledger** that records statements, evidence, assumptions,
  confidence, falsifiers, expiry, refutation, and supersession separately from
  operational status.
- **Context separation** inspired by durable workspace/memory patterns: Planner,
  Executor, and advisors receive separate bounded Context Packs instead of full
  transcripts and raw logs.
- **ChatGPT Project research partner Skill** that lets init choose Codex's
  built-in browser or Chrome, creates one dedicated ChatGPT Project, verifies an
  exact Pro model label, and tracks new consultations and true follow-ups.
- **Claude Code and Grok Build adapters** for independent methodology review and
  real-time/divergent scouting, selected dynamically at init.
- **agmsg-compatible communication policy** for local long-lived sessions,
  including Windows Git Bash guardrails.
- **GitHub Project control plane** generated from a repository-owned
  specification: fields, labels, Issues, and browser-completed views.
- **Windows bootstrap and Doctor** with no required Python runtime dependencies.
- **Kaggle preset** for safe CLI readiness checks, data inventory, evaluation
  contracts, and no accidental setup submissions.
- **Human comprehension layer** with concise Japanese briefs and deterministic
  Mermaid/SVG/HTML visualizations.
- **Tests and CI on Windows and Linux**.

## Quick start on the Windows research host

```powershell
git clone https://github.com/Aero123421/Research-Olacle.git my-research
cd my-research
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap.ps1 -Initialize
```

The initial bootstrap writes only ignored local discovery/interview state, so the
template clone remains clean. Before materializing setup files, adopt it as the
private research repository:

```powershell
researchctl repo adopt OWNER/NEW-RESEARCH-REPO --visibility private
```

Open the folder in Codex in the ChatGPT desktop app, then say:

```text
このリポジトリを新しいAI Research Labとして初期化してください。

私の要望:
このKaggleコンペでPrivate Leaderboard 1位を狙いたい。
技術的な方法は任せる。既存手法だけでなく大胆な案も調べてほしい。

対象:
https://www.kaggle.com/competitions/...

AGENTS.mdとBOOTSTRAP.mdに従い、読み取り専用の環境調査、必要な面談、
GitHub Project、ChatGPT研究Project、Doctor、ResearchPlan、最初の
設定済みResearch Executor Campaign開始まで進めてください。
```

See [BOOTSTRAP.md](BOOTSTRAP.md) for the complete idempotent setup contract.

## Core commands

```powershell
researchctl init --answers .research-lab\local\init-answers.json
researchctl doctor --profile quick
researchctl repo adopt OWNER/NEW-RESEARCH-REPO --visibility private
researchctl doctor --profile full
researchctl github setup
researchctl plan create --intent-file mission.txt --target "https://..."
researchctl context planner
researchctl campaign create --title "..." --goal "..."
researchctl campaign validate C-001
researchctl campaign activate C-001
researchctl context executor C-001
$claim = researchctl campaign claim-executor C-001 --session-id <GOAL_SESSION_ID> --worktree <WORKTREE> | ConvertFrom-Json
$claimId = $claim.executor.claim_id
researchctl loop checkpoint
researchctl loop instruction
researchctl campaign checkpoint C-001 --claim-id $claimId --expected-revision <REVISION> --patch checkpoint.json
researchctl job register --campaign C-001 --name "quick validation" --resource GPU0 --planned-hours 1 --claim-id $claimId
researchctl job start <JOB_ID> --claim-id $claimId
researchctl claim-ledger record --statement "..." --confidence 0.4 --falsifier "..."
researchctl brief
researchctl visualize
```

Run `researchctl --help` for the complete CLI. The Director can call
`researchctl loop status` at any time to determine whether to run Planner, start
or monitor one fresh Executor, resume Planner after Handoff, complete the Mission,
or repair contradictory state.

## Runtime boundary

`researchctl loop` is a deterministic governance and recovery harness. It does
**not** launch an AI process by itself. The Codex App Director, a scheduled task,
or a provider-specific adapter executes the rendered instruction. Unattended
remote execution is only as strong as that adapter; without a reviewed
launch/status/cancel implementation, cancellation remains cooperative.

## Repository as template, not a central service

This repository is intentionally self-contained. Clone it once, then convert the
clone into a private research repository:

```powershell
researchctl repo adopt OWNER/NEW-RESEARCH-REPO --visibility private
```

The original remote becomes `template-upstream`; the new research repository
becomes `origin`. Adoption then materializes the reviewable setup files in the
new repository, ready for a Setup PR. Discovery, Doctor, browser sessions,
ChatGPT Project URLs, process IDs, and host-specific paths remain under ignored
local state until adoption succeeds.

## Research roles

| Role | Scope |
|---|---|
| Research Director | Human conversation, control-plane observation, starting/resuming loops |
| Research Planner | Broad research landscape, EDA, evaluation risk, strategy and Campaign Contract |
| Research Executor | One fresh configured runtime-profile Campaign to success or withdrawal |
| ChatGPT Pro partner | General senior research partner; role intentionally not narrowed |
| Claude auditor | Independent methodology, CV, leakage, and falsification review |
| Grok scout | X/community signals and divergent hypotheses |

Models and effort labels are discovered during init. Stable roles are stored in
configuration; actual model IDs and UI labels are local runtime facts.

## Context model

1. **Constitution** — small invariant instructions (`AGENTS.md`).
2. **Role Skill** — Planner or Executor procedure, loaded only when needed.
3. **Current Context Pack** — bounded evidence for the current job.
4. **Durable Memory** — verified strategic findings, decisions, and the append-only claim ledger on disk.
5. **Archive** — logs, artifacts, full consultation responses, models, and raw
   evidence; searched only when a decision requires it.

Planner never receives the Executor's complete conversation. Advisors receive a
Question Pack, not the whole repository. Campaign state is durable on disk and
in GitHub, so a session can stop or compact without destroying the research.

## Browser-based ChatGPT Project integration

During init, choose one:

- **Codex built-in browser** — isolated and convenient inside the ChatGPT desktop
  app.
- **Chrome** — persistent signed-in profile using the official Codex Chrome
  extension installed from the ChatGPT/Codex Plugins directory. A dedicated profile is recommended.

The Skill uses semantic UI checks, never blind coordinate macros. It verifies:

- correct ChatGPT Project URL and name
- project-only memory when available
- exact configured Pro model label
- selected-model badge after closing the picker
- conversation URL and response capture

It never silently falls back to a weaker model. Authentication or UI failure
marks consultation as degraded; the autonomous Planner–Executor loop continues
with available evidence and advisors.

## Scope and safety

Scientific tactics are autonomous inside the Contract. Human-owned boundaries
remain explicit: mission/value choices, credentials/MFA, terms acceptance, data
and legal policy, new paid providers, hard-budget increases, public release, and
destructive or irreversible external actions.

A budget or policy violation records a cancellation request; it is not evidence
that the external process stopped. A running Job becomes `cancelled` only after
an auditable PID, scheduler/provider Job ID, status record, or equivalent stop
reference is supplied. Paid compute fails closed unless a reviewed code adapter
can both enforce cancellation and obtain provider-side cost measurements. Every
backend must explicitly declare whether it is paid; a paid backend also requires
a positive per-Job cost estimate, so `planned_cost_jpy = 0` cannot bypass those
controls.

Kaggle rules and data-sharing constraints always apply. External advisors receive
only the minimum necessary context; raw competition data stays local by default.

## Development

The project is currently **alpha**: the protocol and local control plane are tested,
but provider-specific enforced-cancellation adapters are not shipped yet.


```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\researchctl.exe self-test
.\scripts\verify.ps1
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md),
[`docs/architecture.md`](docs/architecture.md), and the reviewed
[upstream reference list](docs/UPSTREAM_REFERENCES.md).

## Independent project notice

Codex Research Harness is an independent open-source project and is not
affiliated with or endorsed by OpenAI, Anthropic, xAI, GitHub, Kaggle, or Nous
Research. Product names and trademarks belong to their respective owners.

## License

Apache License 2.0. See [LICENSE](LICENSE).
