# Changelog

## Unreleased

- keep pre-adoption initialization and Doctor output in ignored local state
- add integrity manifests and hash validation for Planner/Executor Context Packs
- add atomic Executor claim, lease, heartbeat, and duplicate-launch prevention
- enforce Campaign, daily GPU, paid-compute, backend, and physical-resource limits
- add cross-platform repository locks for IDs and mutable ledgers
- pin development tooling and GitHub Actions; test Python 3.11–3.13 and Windows wrappers
- replace the misleading quick Doctor-only secret workflow with full-history Gitleaks scanning
- replace generic lifecycle patching with explicit revisioned ResearchPlan and
  Campaign transitions
- bind active Campaign and Job mutations to fenced Executor claims with monotonic
  generations; stale takeover now requires outstanding Job reconciliation
- separate Campaign phase from ownership, preserve Executor history, and reject
  stale `expected_revision` writes
- register typed compute resources, reject unknown or backend-mismatched devices,
  and enforce Campaign/daily/monthly capacity and cost admission
- distinguish cancellation requests from confirmed process termination; running
  Job cancellation requires an auditable external stop reference
- fail paid compute closed unless a reviewed control adapter implements enforced
  cancellation and provider-side cost metering
- add append-only epistemic claims with evidence, assumptions, confidence,
  falsifiers, expiry, refutation, and supersession
- add trust classes, inclusion reasons, exclusions, and integrity manifests to
  bounded Context Packs
- strengthen Campaign Contracts and Handoffs with counter-hypotheses, metric
  gaming risks, reversal evidence, adoption exclusions, observations,
  inferences, uncertainty, and epistemic residue
- make Campaign/Plan ID ordering numeric and harden cross-platform lock ownership,
  stale detection, and token-checked release
- replace model IDs in core Campaign state with configurable runtime profiles and
  document human-owned constitutional authority
- classify the 0.1.x line as Alpha and document the boundary between deterministic
  orchestration and provider-specific execution

## 0.1.0 — 2026-07-15

- Initial Windows-first Codex Research Harness template
- Research Planner and GPT-5.6 Sol High Goal Mode Executor Skills
- bounded context, Campaign Contract, checkpoint, and Handoff protocols
- durable Planner/Executor loop state machine and Director instructions
- ChatGPT Project partner with built-in-browser/Chrome choice and exact Pro label
  verification
- GitHub Project control-plane specification and setup
- Codex/Claude/Grok/agmsg/Kaggle/GPU readiness probes
- deterministic human brief and visualization outputs
- standard-library CLI, PowerShell bootstrap, tests, and cross-platform CI
