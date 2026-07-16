# Initial setup interview

The first-run interview exists to collect **human values and external limits**, not facts that the host can discover automatically.

## Interaction rules

- Probe first; do not ask which tools are installed before checking.
- Ask one decision at a time in plain Japanese.
- Give a recommended choice and a short reason.
- Avoid product jargon unless it changes the decision.
- Do not turn routine scientific choices into approval prompts. The human still owns the Mission, value trade-offs, data/legal boundaries, hard budgets, public release, and irreversible external actions.
- Save answers under `.research-lab/local/`; never store credentials.
- Resume from existing answers after interruption instead of restarting the interview.

## Decisions to collect

### 1. Explanation profile

Ask how much detail is useful, which terms need first-use explanations, whether charts are preferred, and whether updates should be event-driven or daily. This affects only the human-facing explanation layer; it never lowers research rigor.

### 2. ChatGPT browser route

Offer:

- **Codex built-in Browser** — isolated browser operated inside ChatGPT/Codex.
- **Official Codex Chrome extension** — uses a chosen Chrome profile and its existing signed-in state.

Record the choice with `researchctl chatgpt browser`. Do not switch routes silently during recovery.

### 3. ChatGPT Project policy

Create exactly one dedicated ChatGPT Project per research repository. Request project-only memory during creation when available. Inspect the live model picker and require an exact visible `Pro` label; no fallback is permitted.

### 4. Compute limits

Collect local GPU availability windows, default Campaign GPU budget, paid-compute hard limits, allowed providers, and automatic shutdown requirements. The Planner allocates resources inside these limits without waiting for routine per-experiment approval; changing the human-owned hard limits requires explicit authority.

### 5. External boundaries

Credentials/MFA, terms acceptance, a new paid provider, hard-budget increases, publication, and destructive external actions require an external action. Pause only the affected capability; continue the rest of the research loop.

### 6. Original mission

Preserve the user's wording in `research/USER_INTENT.md`. The Planner may clarify background and target, but it must not prematurely translate a vague goal such as “win this competition” into one narrow model technique.

## Machine-readable example

Copy `.research-lab/init-answers.example.json` to the ignored path below, edit only the answers that differ, then initialize:

```powershell
New-Item -ItemType Directory -Force .research-lab\local | Out-Null
Copy-Item .research-lab\init-answers.example.json .research-lab\local\init-answers.json
researchctl init --answers .research-lab\local\init-answers.json
```
