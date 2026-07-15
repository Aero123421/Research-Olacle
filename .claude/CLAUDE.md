# Claude Code adapter

This repository's research protocols live under `research/protocols/`. Do not
duplicate or silently reinterpret them here.

For methodology review, invoke the project subagent `methodology-auditor`. It is
read-only and receives one bounded Question Pack, not the whole Planner or
Executor transcript. Return an evidence-linked audit; the caller persists it
under `research/consultations/<Q-ID>/`.

Never change the Mission, Campaign Contract, evaluation contract, or research
state while acting as an auditor.
