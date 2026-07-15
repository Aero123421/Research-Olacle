# ChatGPT Project integration

The ChatGPT Project is a browser-operated general senior research partner.
There is one Project per research repository and many question-specific chats.

## Browser choice

At init the human chooses:

- Codex built-in browser
- Chrome with the official Codex Chrome extension and preferably a dedicated profile

The choice is local and can be changed deliberately after re-verification. Do not
switch silently as error recovery.

## Project state

`.research-lab/local/chatgpt.json` records:

- browser mode
- exact Project name and URL
- exact required Pro model label
- preference list
- verification timestamp/status

No credentials or cookies are stored by the harness.

## Model stability

The UI is inspected at runtime because labels and account access can change. The
Skill exact-matches the configured Pro label and verifies the selected badge.
No silent fallback is allowed. A missing model degrades ChatGPT consultation but
does not stop core research.

## Conversation lineage

- new scientific question or independent opinion → new Project chat
- clarification or extension of the same question → saved conversation URL

Each consultation has `REQUEST.md`, `RESPONSE.md`, and `META.json` under
`research/consultations/Q-XXXX/`.
