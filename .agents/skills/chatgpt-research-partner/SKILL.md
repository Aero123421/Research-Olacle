---
name: chatgpt-research-partner
description: Use a dedicated ChatGPT Project as a general senior research partner through either the Codex built-in browser or Chrome, selected at init. Create/reuse the Project idempotently, configure project-only memory and research instructions, select and verify an exact Pro model label, submit new questions or true follow-ups, capture responses and URLs, and recover safely from login/UI failures. Use for Planner or Executor consultations; never silently fall back to another model.
---

# ChatGPT Project Research Partner

ChatGPT Pro is a broad senior research partner. Do not constrain it to literature
review or critique: use it for reframing, domain knowledge, data interpretation,
strategy, experimental design, cross-domain transfer, anomalies, implementation,
and synthesis when valuable.

## Read local policy first

Read:

- `.research-lab/local/browser.toml`
- `.research-lab/local/chatgpt.json` if present
- `.research-lab/config/agents.toml`
- the consultation `REQUEST.md`

If browser mode has not been selected, explain both choices in plain Japanese and
ask one question:

- **Codex built-in browser:** isolated and convenient inside the desktop app.
- **Chrome:** persistent signed-in profile with the official Codex Chrome extension; use a
  dedicated profile and do not run parallel automation in the same browser.

Record selection with:

```powershell
researchctl chatgpt browser built_in
# or
researchctl chatgpt browser chrome --chrome-profile "Research Automation"
```

## Authentication boundary

Open ChatGPT. If logged out, ask the human to complete login/MFA. Never type,
read aloud, store, screenshot for Git, or copy credentials. Verify that the
intended account/workspace is active after login.

## Idempotent Project initialization

1. If local state has a Project URL, open it and verify the title. Do not create a
   duplicate because the sidebar is temporarily slow.
2. If there is no state, search the ChatGPT Project list for an exact matching
   research name. Recommended name:

   `CRH • <owner>/<repo> • <short repository fingerprint>`

3. Reuse only if the name and repository identity match. Otherwise create one new
   Project.
4. Enable **project-only memory** when the UI offers it.
5. Add the instructions in `templates/project-instructions.md`.
6. Save the actual Project URL only through:

```powershell
researchctl chatgpt record-project --browser <built_in|chrome> \
  --name "<exact title>" --url "<project URL>" \
  --model-label "<exact selected label>" \
  --preference "Pro"
```

The local URL/state is Git-ignored. The committed setup report contains no
session identifiers or credentials.

## Exact Pro model selection

The UI and available labels can change. Never assume a coordinate or a model
name from memory.

1. Open the model selector in the message composer.
2. Read all visible labels. Match the local preference list exactly, in order.
3. Select the exact label **Pro**. Current OpenAI documentation maps this to
   GPT-5.6 Sol Pro in standard ChatGPT. Do not treat `Pro Standard` or
   `Pro Extended` as equivalent: those labels can refer to a different model in
   managed workspaces. If exact `Pro` is unavailable, mark the integration
   degraded and do not silently use Instant/Medium/High/Extra High or another
   Pro variant.
4. Close the picker.
5. Verify the selected label is visibly active in the composer.
6. Before a critical question, verify again. When Chrome Developer Mode/semantic
   DOM access is available, prefer accessible names/text over coordinates.
7. Record verification:

```powershell
researchctl chatgpt verify-project --model-label "<exact visible label>" --url "<project URL>"
```

A click without post-condition verification is a failure.

## New question versus follow-up

### Create a new Project chat when

- the research question, hypothesis family, or decision changes
- independent judgment is needed without anchoring from an earlier answer
- a new Campaign begins

Prepare it first:

```powershell
researchctl chatgpt prepare \
  --requester research-planner \
  --purpose "strategy synthesis" \
  --question "..." \
  --context research/plans/RP-001/evidence/eda-summary.md
```

Open a new chat inside the saved Project, verify Pro, submit the generated
`REQUEST.md`, attach only the minimum permitted files, and capture the complete
response.

### Use a saved conversation URL when

- asking for clarification, criticism, extension, or synthesis of the same
  question and evidence lineage
- the previous response is intentionally part of context

Pass `--follow-up-to <Q-ID>` when preparing the new request, open the conversation
URL recorded in that question's `META.json`, verify Project and Pro model, then
submit the follow-up.

Do not use one giant lifelong chat for unrelated research questions.

## Response capture

After completion:

1. Verify the response finished and did not end on an error/retry state.
2. Copy the response faithfully into a temporary local file.
3. Record the conversation URL and exact active model label:

```powershell
researchctl chatgpt record-response Q-0001 \
  --url "<conversation URL>" \
  --response-file "<temporary response file>" \
  --model-label "<exact visible label>"
```

4. Planner/Executor must write a bounded, evidence-oriented synthesis to a temporary file and record it with:

```powershell
researchctl chatgpt record-synthesis Q-0001 --file "<temporary synthesis file>"
```

5. Preserve the full response as archive evidence, but only `SYNTHESIS.md` is automatically eligible for another role's Context Pack. Distinguish advisor claims from experimental evidence.

## Stable UI operation

- Use semantic text, accessible labels, and URL/title checks. Avoid hard-coded
  screen coordinates and brittle pixel macros.
- Do not run two browser-control tasks against the same browser/profile.
- After navigation, wait for stable UI and verify page identity before clicking.
- Critical actions get at most two retries. On uncertainty, stop the affected
  consultation, preserve state, and continue the research loop with other
  advisors/evidence.
- Never create another Project as a generic recovery step.

## Failure states

- Login expired → `needs_login`; human completes login; resume same Project URL.
- Model missing → `degraded`; no silent fallback; other research continues.
- Project URL invalid → verify sidebar/search before recreating.
- Chrome extension disconnected → reconnect plugin/profile; do not switch
  browsers without updating local policy.
- UI changed → use semantic inspection and update this Skill through a tested PR,
  not an ad-hoc coordinate workaround.
