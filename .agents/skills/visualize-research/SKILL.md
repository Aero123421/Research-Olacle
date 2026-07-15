---
name: visualize-research
description: Produce low-cognitive-load, evidence-faithful research visualizations from durable campaign and experiment state. Use for human cockpit updates, campaign map, GPU timeline, evidence trajectory, and PR summaries. Generate numerical/state graphics deterministically; use generative images only when the human explicitly requests an illustrative concept image.
---

# Visualize Research

Run:

```powershell
researchctl visualize
```

This generates deterministic Mermaid, SVG, and HTML outputs from state. Never use
generative imagery for scores, dates, GPU usage, dependencies, or audit evidence.
Keep the visual layer separate from the research state of record.
