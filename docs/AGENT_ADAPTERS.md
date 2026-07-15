# Agent adapters

Codex is the research harness and source of orchestration. Claude Code and Grok
Build are optional, independently authenticated advisors. Their project files are
thin adapters over the common protocols in `research/protocols/`; this prevents
three drifting copies of the research method.

## Claude Code

- Project subagent: `.claude/agents/methodology-auditor.md`
- Project Skill: `.claude/skills/methodology-audit/SKILL.md`
- Default behavior: read-only, independent methodology/CV/leakage/falsification
  audit of one Question Pack.
- The concrete Claude model and effort are discovered and tested during init. The
  adapter deliberately uses `model: inherit` so a new best model can be selected
  without changing the research protocol.

Verification on the Windows host:

```powershell
claude --version
claude auth status --text
claude doctor
```

Restart a running Claude Code session after adding a new `.claude/agents` folder.

## Grok Build

- `.grok/skills/x-research-scout/SKILL.md`
- `.grok/skills/divergent-research-scout/SKILL.md`

The init census must verify `grok inspect --json`, `grok models`, headless output,
and actual X/web search with attributable sources. Model recency alone is not
evidence of live search.

```powershell
grok version
grok inspect --json
grok models
grok -p "Return a JSON smoke response" --output-format json
```

## ChatGPT Project partner

This is a browser Skill, not an API adapter. Init chooses the Codex built-in
browser or Chrome. Project and conversation URLs remain local. Exact visible
model label `Pro` must be selected and verified after every critical navigation;
no silent model fallback is allowed.
