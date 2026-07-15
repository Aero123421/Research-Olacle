# Bootstrap a new AI Research Lab

This document is the canonical first-run procedure. It is written so a human can
clone one repository, open it in Codex on the Windows research host, state a
vague research goal, and let Codex create the complete research environment.

日本語の簡易説明は [`docs/ja/はじめに.md`](docs/ja/はじめに.md) を参照してください。

## User experience

1. Clone this repository on the always-on Windows research host.
2. Open the cloned folder in Codex in the ChatGPT desktop app.
3. Tell Codex the vague mission, target (for example a Kaggle URL), and any hard
   deadline you already know.
4. Codex inspects first. It only asks questions that require human values or
   external action, using plain Japanese and one decision at a time.
5. Codex creates the local lab state, GitHub control plane, ChatGPT research
   Project, agent roster, compute policy, and readiness report.
6. After final Doctor checks, Research Planner opens a Draft ResearchPlan PR,
   performs EDA/domain research/advisor consultation, and issues the first
   Campaign Contract.
7. GPT-5.6 Sol High starts that Campaign in Goal Mode. Research continues without
   routine human approval.

## 0. Do not improvise

The Markdown files describe intent. Deterministic changes must go through
`researchctl` or the scripts shipped in this repository. Re-running setup must
resume or repair existing state, not create duplicates.

## 1. Install the local CLI on Windows

From PowerShell in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap.ps1 -Initialize
```

The script:

- locates Python 3.11+
- creates `.venv`
- installs this repository in editable mode without fetching runtime packages
- runs the quick Doctor
- optionally initializes ignored local answers
- keeps the template clone commit-clean so repository adoption can run next

Before adoption, Doctor outputs are stored under `.research-lab/local/setup/`.
Tracked setup reports are materialized only after adoption succeeds.

The base harness has no runtime Python dependencies. Data-science extras are
installed only when the Planner needs them:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[data]"
```

## 2. Read-only discovery before questions

Run:

```powershell
researchctl doctor --profile full
```

Inspect, without modifying authentication:

- Git and repository state
- GitHub CLI login and `project` scope
- Codex installation and `codex login status`
- Claude Code installation and `claude auth status --text`
- Grok Build configuration and models
- agmsg plus the correct Git Bash path on Windows
- Kaggle CLI safe read access
- CPU/disk/NVIDIA GPU
- browser availability
- existing ChatGPT Project local state
- credential hygiene

Explain the result in Japanese before asking for external action.

## 3. Minimal setup interview

Ask only what cannot be discovered. Offer a recommendation and one plain-language
choice at a time.

Required values:

1. **Human explanation profile** — conclusion-only, concise reasons, or technical
   detail; terms explained on first use; event-driven or daily updates.
2. **Browser for ChatGPT Project work** — Codex built-in Browser, or Chrome with
   the official Codex Chrome extension installed from Plugins. Chrome should use a dedicated signed-in profile.
3. **ChatGPT Pro policy** — inspect the actual model picker, choose the exact Pro
   label available to the account, and record a preference order. No silent
   fallback.
4. **Compute boundaries** — local GPU hours, allowed times, paid compute hard
   limits, approved providers, and auto-shutdown requirements.
5. **External-action policy** — credentials, terms, destructive operations,
   publication, and submission policy. Scientific decisions remain autonomous.
6. **Original mission** — preserve the user's wording in
   `research/USER_INTENT.md`; do not prematurely translate it into a narrow
   technique.

A documented starting point is `.research-lab/init-answers.example.json`; see
[`docs/INITIAL_INTERVIEW.md`](docs/INITIAL_INTERVIEW.md). Save the chosen answers
to a local JSON file and run:

```powershell
researchctl init --answers .research-lab\local\init-answers.json
```

## 4. Convert the template clone into the research repository

When the clone still points at the OSS template, keep the tracked tree pristine
and use:

```powershell
researchctl repo adopt OWNER/NEW-RESEARCH-REPO --visibility private
```

This renames the old `origin` to `template-upstream`, creates the new repository,
adds a new `origin`, and pushes. The command refuses a dirty tree, rolls the
remote name back if creation fails, and only after success materializes the
tracked setup profile/policy files for the Setup PR.

## 5. Create the GitHub Project control plane

First ensure GitHub CLI is authenticated:

```powershell
gh auth login
gh auth refresh -s project
```

Then:

```powershell
researchctl github setup
```

This idempotently creates or reuses:

- one repository-linked GitHub Project
- custom fields from `.research-lab/project-spec.json`
- research labels
- Mission, initial Strategy, and readiness Issues

GitHub CLI does not expose a stable command for creating saved Project view
layouts. Invoke `github-project-setup` using the selected browser to create and
verify the Cockpit, Now, Timeline, GPU Queue, By Agent, Evidence, Exceptions,
and Results views. The exact specification is in
[`docs/GITHUB_PROJECT_SETUP.md`](docs/GITHUB_PROJECT_SETUP.md).

## 6. Initialize the ChatGPT general research partner

Invoke `chatgpt-research-partner`.

The skill must:

1. Use the selected Codex built-in browser or Chrome profile.
2. Open ChatGPT and ask the human to complete login/MFA only when necessary.
3. Reuse an existing matching Project if local state proves it is the same
   project; otherwise create exactly one Project named for the repository.
4. Enable project-only memory when offered.
5. Apply the project instructions shipped with the skill.
6. Inspect the live model selector, choose the configured exact Pro label, and
   verify the selected badge after closing the picker.
7. Save Project URL, browser mode, model label, and verification timestamp under
   `.research-lab/local/chatgpt.json`.
8. Run one harmless research-quality smoke question and record the conversation
   URL and response under `research/consultations/`.

Credentials, cookies, profile paths containing secrets, and MFA data never enter
Git or PRs.

## 7. Initialize other advisors

At init, inspect current capabilities rather than hard-code model names:

- Claude Code: independent methodology/ leakage/ falsification audit
- Grok Build: X/community search and divergent hypotheses; verify real X search
  with source links rather than assuming model recency
- agmsg: local notification transport among long-lived sessions; on Windows pin
  Git Bash, never the WSL shim

ChatGPT Pro is a broad senior research partner, not a narrow specialist. Planner
and Executor may consult it on strategy, data interpretation, domain knowledge,
experimental design, cross-domain transfer, anomalies, implementation tradeoffs,
or reframing.

## 8. Final readiness gate

Run:

```powershell
researchctl doctor --profile full
researchctl self-test
python -m unittest discover -s tests -v
```

Readiness is separated by capability. Optional advisor failures do not block the
core loop. A missing login pauses only that advisor.

## 9. Start Research Planner

Create or update a Draft ResearchPlan PR. Planner runs in an isolated context and
uses `research-planner`.

Planner must:

- preserve the vague mission
- inspect competition rules and current state
- perform reproducible EDA and data-science diagnostics
- understand the data-generating process
- reproduce or diagnose a baseline and evaluation contract
- survey core and adjacent domain knowledge, historical and negative results,
  analogous problems in other fields, public solutions, Discussions, and current
  community signals
- independently consult ChatGPT Pro, Claude, and Grok when useful
- maintain Primary, Hedge, Wildcard, Dormant, and Rejected strategy lanes
- choose the Campaign that maximizes research value now—not merely the first
  plausible model tweak
- issue measurable success and withdrawal conditions plus wall/GPU/cost budgets

Create the durable ResearchPlan state first, preserving the original mission:

```powershell
researchctl plan create --intent-file mission.txt --target "<target URL or description>"
```

Then build the bounded Planner pack:

```powershell
researchctl context planner
```

## 10. Start Goal Mode Research Executor

After validating the Campaign Contract:

```powershell
researchctl campaign validate C-001
researchctl campaign activate C-001
researchctl context executor C-001
researchctl campaign claim-executor C-001 --session-id <GOAL_SESSION_ID> --worktree <WORKTREE>
```

The claim is an atomic `ready → executing` transition and binds the Campaign to
one session, owner, lease, and worktree. Only after the claim succeeds, open the
fresh GPT-5.6 Sol High session, read
`research/campaigns/C-001/GOAL_PROMPT.md`, and start `/goal`. A second live claim
is rejected.

One Campaign gets one Executor context. The Executor may create hypotheses,
implement, run experiments, analyze evidence, and consult advisors. It may not
change Mission, fixed evaluation, or resource limits. At checkpoints invoke
`context-checkpoint`. At completion invoke `campaign-handoff` and return evidence
to Planner.

## 11. Continue the loop

Planner resumes from strategy memory and Campaign Handoff—not the Executor's full
conversation. It updates the research landscape and issues the next Campaign.
Every few Campaigns or after a major premise change, start a fresh Planner epoch
from durable files to reduce anchoring.

Use the durable loop controller rather than remembered conversation to decide each
transition:

```powershell
researchctl loop checkpoint
researchctl loop instruction
```

The rendered instruction tells the Director to start/run Planner, start/monitor one
fresh Executor, resume Planner after Handoff, complete the Mission, or repair state.
