#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
"$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or later is required")
PY
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -e .
.venv/bin/researchctl doctor --profile quick || true
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/researchctl self-test
printf 'Installed. Open %s in Codex and follow AGENTS.md + BOOTSTRAP.md.\n' "$ROOT"
