# CB1 Mobile Tax Settlement and Adjustment Implementation Plan

> Execution remains local and stacked on the reviewed tax evidence/liability slice. Do not run production writes, SQL migrations, merges, deployments, signing, or releases.

## Task 1: Freeze backend Mobile/candidate contracts with failing tests

- Update settlement and adjustment API contract tests to require same-handler `/api/mobile/v1/...` aliases, pagination coordinates, candidate payloads, and permission flags.
- Add repository contract assertions for exact server-derived candidate queries and for continued use of protected PostgreSQL write functions only.
- Run the focused backend contract tests and record the expected red state.

## Task 2: Implement read-only candidate derivation and shared handlers

- Add immutable candidate dataclasses and read queries to the settlement and adjustment repositories.
- Add strict candidate serialization helpers and Mobile aliases to the existing routers.
- Include `limit`, `offset`, policy flags, candidates, items, summary, permissions, and notice in each read payload.
- Keep every mutation delegated to the existing protected PostgreSQL functions.
- Run focused backend contract tests and compile checks.

## Task 3: Build fail-closed Flutter settlement models and repository test-first

- Add tests for overview/summary/item/candidate parsing, invalid state rejection, return evidence recording, payment evidence recording, preparation, and exact posting requests.
- Implement strict models and the HTTP repository using the Mobile aliases, bearer token, and approved-device header.
- Run focused Dart tests.

## Task 4: Build fail-closed Flutter adjustment models and repository test-first

- Add tests for overview/summary/item/candidate parsing, server-derived kind enforcement, adjustment evidence recording, preparation, and exact posting requests.
- Implement strict models and the HTTP repository.
- Run focused Dart tests.

## Task 5: Add Management Mobile workspaces test-first

- Add launcher tests and page tests for settlement and adjustment discoverability, summaries, queue rows, permission gating, candidate selection, exact totals, retained-evidence forms, and separate Management review confirmations.
- Implement the settlement and adjustment pages using compact row/card layouts suitable for Mobile.
- Update the tax-accounting launcher and review mutation inventory without removing existing protected confirmation rules.
- Run focused widget tests and affected analyzer/formatter checks.

## Task 6: Verify the entire stack

- Run focused backend and Flutter suites.
- Run touched-file formatting and analyzer.
- Run full Flutter and backend regression suites.
- Run Python compile checks and explicit diff/status checks proving `architecture-map.json` remains unrelated and unstaged.
- Review the resulting diff against this spec and security/accounting invariants.

## Task 7: Publish evidence without claiming human/release completion

- Commit only explicit slice files on a stacked `codex/` branch.
- Push and open a draft PR against the exact preceding tax slice.
- Wait for exact-head GitHub Actions and record workflow evidence.
- Update the draft PR, Master Issue #296, and the authoritative Notion status page with implemented behavior, verification, remaining scope, and unchanged human/release gates.
