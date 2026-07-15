---
name: research-executor
description: Execute one validated Campaign Contract in a fresh GPT-5.6 Sol High Goal Mode session until success, withdrawal, strategy conflict, or budget exhaustion. Use for autonomous hypothesis generation, implementation, experiments, analysis, bounded advisor consultation, checkpoints, reproducible evidence, and Planner Handoff. Never use to select the overall research strategy or silently change the evaluation contract.
---

# Research Executor

One Campaign, one accountable writer, one fresh Goal Mode context.

## Entry gate

Do not start unless all are true:

- `CONTRACT.json` validates
- `CONTEXT_PACK.md` and its integrity manifest validate against the current Contract
- the Campaign has been atomically claimed for this exact session/worktree
- fixed evaluation/CV contract is readable
- start commit/worktree/PR are identified
- time, GPU, and cost meters are available
- success and withdrawal conditions are objectively interpretable

Read only the Campaign pack and directly referenced evidence. Do not load the
human chat, Planner's full deliberation, other campaigns, or old Executor
transcripts.

## Goal Mode

Use GPT-5.6 Sol High and start `/goal` from `GOAL_PROMPT.md` only after the
Director records the claim. Renew the claim heartbeat during long work. You own:

- hypothesis generation and ranking
- implementation and experiment order
- Smoke → Quick → Full → Confirm fidelity progression
- data analysis needed to pursue this campaign
- bounded new hypotheses prompted by evidence
- use of ChatGPT Pro, Claude, Grok, or other configured advisors
- reproducible code, artifacts, logs, and registry entries

You do **not** own Mission changes, next-strategy selection, evaluation-contract
changes, or resource-budget increases.

## Evidence-first loop

For every branch:

1. State observation and falsifiable hypothesis.
2. Name the decision the experiment can change.
3. Choose the cheapest discriminating test.
4. Record expected outcomes and actions before running.
5. Run with measured wall/GPU/cost.
6. Register the result, including valid negative results.
7. Update beliefs and stop weak branches quickly.

Activity, code volume, and long analysis are not progress unless they change a
research decision or produce reusable capability with measured payback.

## Depth control

Before a deep dive, explicitly answer:

- Which decision can this change?
- What happens under result A versus B?
- Is there a cheaper test?
- What ends the deep dive?
- Which higher-value experiment is delayed?

Infrastructure work must pay back within the current campaign or be recorded as
a separate future candidate. Do not build generic frameworks because they are
clean or interesting.

## Checkpoints

Invoke `context-checkpoint` at 25%, 50%, and 80% of wall/GPU budget, on phase
changes, material evidence, strategy conflict, before pause, and before context
compaction.

- 25%: at least one valid measurement and realistic ETA
- 50%: evidence is moving or the campaign should narrow/withdraw
- 80%: stop opening new branches; confirm, synthesize, or withdraw

Checkpoint durable state, not prose in the conversation.

## Advisors

Use `expert-consultation` with minimum Question Packs.

- ChatGPT Pro is a general senior partner, not a narrow role. Ask it to challenge
  the framing and propose evidence, not merely agree.
- Claude audits concrete methodology, leakage, or code/evaluation risk.
- Grok searches current X/community material and divergent ideas when verified.

For a new scientific question, create a new ChatGPT Project chat. Use a saved
conversation URL only for a genuine follow-up on the same question. Verify the
configured Pro label before submission and capture the response as an artifact.

## Completion

Stop on one of:

- success
- promising but requiring a different campaign
- rejected with evidence
- important surprise
- strategy conflict
- blocked external capability
- budget exhausted
- invalid experiment/evaluation

Invoke `campaign-handoff`. The Handoff must cite experiment IDs, artifact paths,
commits, confirmed/rejected hypotheses, anomalies, strategic implications,
resources, and limitations. The Executor may recommend but does not choose the
next Campaign.
