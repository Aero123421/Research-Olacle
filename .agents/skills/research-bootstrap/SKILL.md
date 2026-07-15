---
name: research-bootstrap
description: Initialize or repair a Codex Research Harness repository on Windows, including environment discovery, plain-language setup interview, GitHub control plane, browser/ChatGPT research Project, agent/compute policies, Doctor, and transition into Research Planner. Use for the first task in a template clone or whenever readiness is incomplete.
---

# Research Bootstrap

Create a reproducible research lab; do not create a one-off setup in chat.

## Required order

1. Read `AGENTS.md` and `BOOTSTRAP.md`.
2. Run `researchctl doctor --profile quick` without changing authentication.
3. Read `.research-lab/local/instance.json` if present. Resume the recorded stage;
   never duplicate external resources.
4. Run the full read-only census: GitHub, Codex, Claude, Grok, agmsg, Kaggle,
   compute, browser, ChatGPT Project local state, and secret hygiene.
5. Explain results in Japanese using ordinary language. Ask only values that
   cannot be discovered, one choice at a time, with a recommended default.
6. Write local setup answers and run `researchctl init --answers <file>`.
7. If this is still a template clone, use `researchctl repo adopt` only after a
   clean commit and explicit repository name/visibility are known.
8. Run `researchctl github setup`; then invoke `github-project-setup` for views.
9. Invoke `chatgpt-research-partner` to select browser, create/verify one ChatGPT
   Project, and verify an exact Pro model label.
10. Verify advisor roles and compute policies. Missing optional advisors degrade;
    they do not block core research.
11. Run full Doctor, self-test, and tests. Write the setup report and Draft setup
    PR.
12. Preserve the user's original wording in `research/USER_INTENT.md` and invoke
    `research-planner`.

## Human interview rules

- Do not ask for model names before inspecting available models.
- Do not ask for hardware details that commands can discover.
- Explain technical terms in one sentence at first use.
- Human values: explanation depth, browser choice, compute/cost limits, external
  actions, mission, deadline.
- Scientific decisions are autonomous and must not become approval questions.

## External action boundary

Never type passwords, MFA codes, payment details, or terms acceptance for the
human. Explain the single required action, wait for completion, verify state,
and continue. Do not expose credentials in terminal output, files, Issues, PRs,
or screenshots committed to Git.

## Completion evidence

Bootstrap is complete only when:

- `research/setup/READINESS.md` exists
- GitHub Project state is recorded locally
- selected browser mode is recorded
- ChatGPT Project URL and exact model label are verified locally
- `research/setup/AGENT_ROSTER.md`, `COMPUTE_POLICY.md`,
  `AUTONOMY_POLICY.md`, and `HUMAN_PROFILE.md` exist
- `researchctl self-test` passes
- no blocking Doctor failures remain
- Research Planner has a bounded context pack and Draft ResearchPlan PR
