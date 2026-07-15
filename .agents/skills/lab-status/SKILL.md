---
name: lab-status
description: Explain the autonomous research lab to a non-researcher without lowering research rigor. Use when the human asks what is happening, whether research is progressing, who is working, GPU/time/cost, what happens next, or whether the harness is healthy.
---

# Lab Status

1. Read `research/setup/HUMAN_PROFILE.md`.
2. Refresh durable facts from GitHub Project/local campaign state, experiment
   registry, compute queue, and latest Handoff. Do not answer from chat memory.
3. Run `researchctl brief` and, when useful, `researchctl visualize`.
4. Lead with a 15-second summary:
   - current campaign/action
   - research signal: stronger, weaker, or uncertain
   - wall/GPU/cost and ETA
   - next event
   - harness health/external boundary
5. Explain at most two new technical terms in a normal update. Put technical
   evidence in a collapsible PR section or linked report.
6. Emphasize changes since the previous update instead of repeating the whole
   mission.

Do not ask the human for routine scientific direction. External action requests
must be concrete and limited to the affected capability.
