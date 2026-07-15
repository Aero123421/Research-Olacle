# GitHub Project setup

GitHub Project is the human control plane, not the experiment database.

## Automated with GitHub CLI

```powershell
gh auth status
gh auth refresh -s project
researchctl github setup
```

The command creates/reuses one Project, links the repository, creates custom
fields and labels, creates seed Issues, and records local Project metadata.

## Browser-completed views

Invoke the `github-project-setup` Skill. It reads
`.research-lab/project-spec.json` and creates/reuses these saved views:

| View | Purpose |
|---|---|
| 00 Cockpit | sparse human overview |
| 01 Now | active work grouped by status |
| 02 Timeline | plan/forecast/deadline roadmap |
| 03 GPU Queue | current/next compute jobs |
| 04 By Agent | accountable roles/runtimes |
| 05 Evidence | campaigns and strategy-changing evidence |
| 06 Exceptions | failures or external boundaries only |
| 07 Results | completed campaigns/outcomes |

The Skill must verify exact names before creation and repair drift instead of
creating duplicate views.

## Update cadence

Local runtime state may update frequently. GitHub updates only on Campaign start,
phase change, material evidence, ETA shift, at-risk/block, handoff, and completion.
PR comments are event-driven, not heartbeat spam.
