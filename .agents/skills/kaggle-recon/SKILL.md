---
name: kaggle-recon
description: Perform safe, rule-aware Kaggle competition reconnaissance for Research Planner: official rules, metric, submission mode, files, deadline, notebook constraints, entered/access state, public/private leaderboard risk, Discussions/public solutions, and a read-only evidence pack. Never submit during setup or assume external data is allowed.
---

# Kaggle Recon

1. Verify official Kaggle CLI and safe read access.
2. Confirm the human account has accepted competition rules; only the human may
   complete terms acceptance.
3. Read official Overview, Data, Evaluation, Rules, Timeline, and Code
   Requirements pages. Store source URLs and dates.
4. Identify metric direction and reproduce its local implementation.
5. Determine CSV versus Code Competition submission and compute/network limits.
6. Inventory files without exposing restricted data to external advisors.
7. Summarize public/private leaderboard structure and overfitting risk.
8. Review relevant Discussions, public notebooks, and analogous competitions as
   hypotheses—not ground truth.
9. Produce a bounded evidence pack for Planner.

Setup and smoke checks are read-only. Never run `kaggle competitions submit`
from this Skill.
