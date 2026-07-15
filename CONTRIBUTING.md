# Contributing

Thank you for improving Codex Research Harness.

## Principles

- Preserve Planner/Executor context separation.
- Keep the base Windows bootstrap dependency-light.
- Prefer deterministic scripts plus inspectable Skills over giant prompts.
- Add evidence and tests for behavior changes.
- Do not hard-code current model names or UI coordinates when runtime discovery
  is possible.
- Never add credentials, browser state, private datasets, or proprietary
  competition artifacts.

## Development

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\researchctl.exe self-test
.\.venv\Scripts\researchctl.exe doctor --profile quick
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\scripts\verify.ps1
```

Linux/macOS:

```bash
./scripts/bootstrap.sh
```

## Pull requests

Keep PRs focused and update relevant Skills, tests, docs, schemas, and ADRs.
Substantial architectural decisions require an ADR under `docs/adr/`. Before a release, complete [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).

## Skill changes

Skills are executable operational policy. Treat third-party content as untrusted.
A changed Skill should include realistic dry-run or fixture tests where possible
and must not broaden permissions silently.
