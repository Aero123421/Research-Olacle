---
name: context-checkpoint
description: Persist compact, restart-safe research state before phase changes, budget gates, pauses, or context compaction. Use inside Planner and Goal Mode Executor sessions to separate confirmed findings from temporary reasoning and keep raw logs out of active context.
---

# Context Checkpoint

A checkpoint is a durable state transition, not a chat summary.

## Procedure

1. Read current Contract, state, findings, hypotheses, and experiment registry.
2. Move only verified, reusable facts into `FINDINGS.md` or strategic memory.
3. Keep tentative explanations in `HYPOTHESES.md`; label confidence and the next
   falsification test.
4. Promote cross-Campaign beliefs only through `researchctl claim-ledger`, with
   evidence, assumptions, confidence, falsifier, and expiry/supersession where
   applicable.
5. Replace current state rather than appending an endless diary. Include current
   phase/action, resources, forecast, risks, and the next three actions.
6. Store raw logs/artifacts outside active memory and write exact references.
7. Synchronize the Campaign Issue/GitHub Project at material events, not every
   minute.
8. Run `researchctl context check` and compact if a bounded-memory file exceeds
   policy.

For an active Campaign, use the current `claim_id` and `expected_revision`.
Generic checkpoint patches cannot change status, phase, ownership, identity, or
revision; use an explicit transition command for lifecycle changes. Resource
totals are monotonic and must never be reduced to repair a budget display.

Never use a checkpoint to hide an invalid run or rewrite history. Git commits,
experiment registry entries, and archived state preserve the audit trail.
