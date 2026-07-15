---
name: github-project-setup
description: Build or repair the GitHub Project research control plane from .research-lab/project-spec.json. Use GitHub CLI for deterministic project, fields, labels, linking, and seed issues, then use the selected browser for idempotent view/filter/layout configuration and verification. Use during bootstrap or when the Project drifts; never create a second Project as a shortcut.
---

# GitHub Project Setup

## Deterministic phase

1. Verify `gh auth status` and `project` scope.
2. Run `researchctl github plan` and review intended fields/views.
3. Run `researchctl github setup`.
4. Reuse the exact Project title recorded in `.research-lab/local/github.json`.
5. Verify repository link, fields, labels, and seed issues. The CLI operations are
   idempotent.

## Browser view phase

GitHub CLI does not provide a stable saved-view creation command. Use the browser
chosen during init and the view specification in `.research-lab/project-spec.json`.

For every required view:

1. Search for exact view name before creating it.
2. Reuse and repair an existing view rather than duplicating it.
3. Configure layout, filter, grouping, visible fields, and date fields as
   specified.
4. Keep the human-facing `00 Cockpit` sparse: Campaign, health/signal, accountable
   role/runtime, current action, progress, wall/GPU time, ETA, next action,
   attention.
5. Verify the saved view by switching away and back.

Required views:

- 00 Cockpit
- 01 Now
- 02 Timeline
- 03 GPU Queue
- 04 By Agent
- 05 Evidence
- 06 Exceptions
- 07 Results

Do not expose local paths, credentials, browser URLs, or raw logs in Project
fields. The Project is the human control plane, not the experiment database.
