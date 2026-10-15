# Changelog

## 1.2.0 - 2026-10-15

- Evaluate dependency verification independently of requirement order and reject dependency cycles.
- Add opt-in causal blocker explanations with shortest paths and deterministic tie breaking in JSON and Markdown.
- Preserve input row order and default report fields/CSV columns; reject CSV plus explanations explicitly.

## 1.1.0 - 2026-07-27

- Added evidence provenance IDs, pass/fail/superseded status, observation and expiration dates, and stale-evidence handling.
- Added contiguous delivery-state gates so a high-level claim cannot skip missing implementation, merge, configuration, deployment, or verification evidence.
- Added acceptance criteria, requirement hierarchy and dependencies, blocked delivery states, failure summaries, previous-snapshot transitions and regressions, and CSV matrix export.

## 1.0.0 - 2026-07-26

- Released the first complete ScopeTrace command-line workflow.
- Added deterministic JSON and Markdown reporting, representative examples, and cross-platform tests.
