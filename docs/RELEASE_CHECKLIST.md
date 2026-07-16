# Release checklist

A release is ready only when the repository can be cloned on a clean Windows
host and the research loop remains recoverable from files alone.

## Code and packaging

- `ruff check .` passes
- `ruff format --check .` passes
- Python sources compile on every supported version
- unit and end-to-end tests pass
- a clean virtual environment can install the package and run `researchctl`
- `researchctl self-test` reports no errors
- Markdown links resolve
- the wheel builds without undeclared runtime dependencies

## Windows path

- `scripts\bootstrap.cmd -Initialize` creates/reuses `.venv`
- PowerShell 5.1-compatible scripts parse and run
- paths containing spaces are handled
- Git for Windows and Git Bash are distinguished from WSL Bash
- ignored local state contains browser URLs, PIDs, machine paths, and credentials

## Research behavior

- Planner and Executor use separate Context Packs
- a draft Contract cannot start `/goal`
- success, withdrawal, wall/GPU/cost budgets, and fixed evaluation are required
- one fresh Executor is used per Campaign
- Campaign and ResearchPlan lifecycle changes reject stale revisions and generic lifecycle patches
- every active Campaign/Job write is bound to the current unexpired fenced Executor claim
- stale claim takeover is blocked until queued/running Jobs are reconciled
- `researchctl loop` derives transitions from durable state
- completion rejects outstanding Jobs and requires an evidence-linked Handoff
- the append-only epistemic ledger can record corroboration, refutation, expiry, and supersession
- optional advisor failure does not stop the core loop
- context manifests record trust classes, inclusion reasons, integrity hashes, and relevant exclusions
- unknown compute resources fail closed; GPU accounting derives from typed resource metadata
- running cancellation is not marked confirmed without external stop evidence
- paid compute is rejected unless a code-registered adapter provides enforced cancellation and provider cost metering
- ChatGPT consultation never silently falls back from the configured exact Pro label

## GitHub control plane

- setup is idempotent
- Project fields, labels, seed Issues, and repository linking are verified
- Campaign status can be resynchronized after interruption
- browser-created views match `.research-lab/project-spec.json`
- no token, Project URL, browser session, or private data is committed

## Documentation

- README and Japanese quick start reflect the current CLI
- `BOOTSTRAP.md` is executable as an init contract
- architectural changes have an ADR
- upstream product assumptions are linked in `docs/UPSTREAM_REFERENCES.md`
- changelog and version are updated
