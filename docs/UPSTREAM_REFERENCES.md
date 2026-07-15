# Upstream design references

This template intentionally owns its workflow and does not require OpenClaw or Hermes Agent. The following official documentation informed the adapters and context boundaries. Re-check current upstream documentation during template upgrades because UI labels and CLI options can change.

## OpenAI / Codex / ChatGPT

- Codex Goal Mode: <https://developers.openai.com/codex/long-running-work>
- Codex Skills: <https://developers.openai.com/codex/build-skills>
- Codex `AGENTS.md`: <https://developers.openai.com/codex/agent-configuration/agents-md>
- Codex subagents: <https://developers.openai.com/codex/subagents>
- Built-in Browser: <https://developers.openai.com/codex/browser>
- Official Codex Chrome extension: <https://developers.openai.com/codex/chrome-extension>
- ChatGPT Projects: <https://help.openai.com/en/articles/10169521-projects-in-chatgpt>
- GPT-5.6 in ChatGPT: <https://help.openai.com/en/articles/11909943-gpt-55-in-chatgpt>

## Claude Code

- Skills: <https://docs.anthropic.com/en/docs/claude-code/skills>
- Custom subagents: <https://docs.anthropic.com/en/docs/claude-code/sub-agents>
- Model and effort configuration: <https://docs.anthropic.com/en/docs/claude-code/model-config>
- Hooks: <https://docs.anthropic.com/en/docs/claude-code/hooks>

## Grok Build

- Overview and headless operation: <https://docs.x.ai/build/overview>
- CLI reference (`inspect`, `models`, login): <https://docs.x.ai/build/cli/reference>

## Context and durable-work inspirations

- OpenClaw context: <https://docs.openclaw.ai/concepts/context>
- OpenClaw memory: <https://docs.openclaw.ai/concepts/memory>
- OpenClaw agent workspace: <https://docs.openclaw.ai/concepts/agent-workspace>
- OpenClaw multi-agent isolation: <https://docs.openclaw.ai/concepts/multi-agent>
- Hermes Agent delegation: <https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation>
- Hermes durable Kanban: <https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban>
- Hermes memory-vs-Skills guidance: <https://hermes-agent.nousresearch.com/docs/guides/tips>

## GitHub

- GitHub Projects: <https://docs.github.com/en/issues/planning-and-tracking-with-projects>
- GitHub CLI Projects: <https://cli.github.com/manual/gh_project>

The borrowed principles are deliberately small: durable file-backed state, independent role contexts, progressive Skill disclosure, evidence-only handoffs, and a task board owned outside any individual agent session.
