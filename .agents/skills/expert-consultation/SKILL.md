---
name: expert-consultation
description: Create minimum-necessary Question Packs and obtain independent advice from the configured ChatGPT Project Pro partner, Claude Code methodology auditor, Grok Build realtime/divergent scout, or other init-verified advisors. Use after forming a provisional analysis. Preserve full responses as artifacts and return only evidence-linked synthesis to the caller.
---

# Expert Consultation

1. State the decision, current evidence, provisional interpretation, uncertainty,
   and expected output.
2. Include only files necessary to answer. Do not send raw restricted data by
   default.
3. Get first responses independently; do not anchor one advisor with another's
   answer.
4. Use `chatgpt-research-partner` for the general senior research partner.
5. For Claude, request methodology/CV/leakage/falsification review with read-only
   permissions unless implementation is explicitly required.
6. For Grok, verify X/web search capability and require source URLs/dates for
   current claims.
7. Store complete responses in `research/consultations/<Q-ID>/` and record model,
   runtime, timestamp, and question lineage.
8. Write a short `SYNTHESIS.md` that separates advisor claims, supporting files,
   uncertainty, and the next discriminating evidence. Full responses never enter
   another role's context automatically.
9. The calling Planner/Executor converts advice into falsifiable hypotheses or
   evidence actions. Advisor agreement is not experimental proof.
