# ADR-0004: Browser-operated ChatGPT Project research partner

Status: accepted

## Context

A strong ChatGPT Pro model is valuable as a broad research partner. UI labels,
model availability, login, and browser preference are dynamic and account-local.

## Decision

At init, the human selects Codex built-in browser or Chrome. A Skill creates or
reuses one dedicated ChatGPT Project, records its URL locally, exact-matches and
verifies the Pro model label, and manages new-question versus follow-up threads.
No separate browser-consultation wrapper or third-party account bridge is assumed.

## Consequences

UI automation needs semantic post-condition checks and graceful degradation.
Credentials remain outside Git. ChatGPT consultation is optional to core state
progress.
