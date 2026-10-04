# Office applications implementation evidence

Implementation authorized by the owner on 4 October 2026: “Go do it.” The visible recent-intake list is required so staff can recognize and reopen saved cases without remembering reference numbers. This record tracks PR497; it is not production or financial-operation approval.

## Baseline

- Existing planning/list clarification: b5971866ab3af7004885fb281f0c3890d3e32d91.
- Deployed main preserved: b5d6962f9baf3edc7cf471e1879151d63220cba5.
- Conflict-free integration baseline: 88553588e977192b98b9083741c6d772b2be1d13.
- `npm test`: 1,637 passed, zero failures/skips.
- `node tools/build_portal.mjs`: passed.
- Actual built Management Office panel captured at 1440/1280/1024/997/768/390/320 CSS-pixel widths (height 857), with a synthetic in-memory API, zero writes and no browser errors. No page overflow in this isolated panel; entry height grows from about 308px at 997 to 697px at 320. This baseline panel capture does not establish full-shell, improved-layout or authenticated-production acceptance.
- Two new actual intake-module regressions fail as expected: editing lookup removes the original unfinished form; starting a new intake retains the old saved reference. Fixes and final evidence pending.

Local working evidence is retained in `.superpowers/sdd/2026-10-03-office-applications-workflow/`: baseline-portal.log, baseline-build.log, baseline-office-browser.json, baseline-office-997.png and task1-red.log. Logs and screenshots contain synthetic data only.

## Requirement coverage

| Requirement | Plan tasks | Current evidence |
| --- | --- | --- |
| New/Continue entry and list visible on opening Office | 2, 5, 7 | Pending |
| Verified case identity and retained unfinished work | 1–4 | Two intake regressions reproduced; fixes pending |
| Truthful case/stage status and explicit saved application | 3, 7 | Pending |
| Protected paginated reads, minimal rows and private logging | 6 | 7ca37271: 935 Office database tests and 77 route/auth/logging regressions passed; independent review pending |
| Management/Employee layouts, keyboard, zoom and PWA | 5, 8 | Baseline panel only; acceptance pending |
| Full integration, review and exact-head CI | 8–9 | Pending |

## Boundaries

Task 6 used a new synthetic PostgreSQL 18 cluster on loopback port 56426. The existing Office validation runner applied the schema through migration 0139 to a disposable database and passed 935 tests with no skips. Both new test files are selected by that runner. Its databases were dropped and the owned cluster stopped. No schema migration was added. Focused query plans covered 10,001 intakes, 1,000 application headers and 10,000 versions; they did not justify a new index.

The broad backend test attempt was stopped at 11% because the host had only 431 MiB of available RAM while two suites ran. It is not a passing result; the full backend remains a final integration/CI requirement. The passing Office run retained one pre-existing Starlette/TestClient dependency warning.

Checked-in Uvicorn and Caddy deployment configuration does not log finder queries. A preserved operator-owned proxy configuration is outside this source verification and must also omit or redact sensitive request queries before release.

No live customer data, database migration, provider operation, financial write, feature activation or deployment is part of this implementation verification. PR496/498 and frozen Master issue296 remain separately owned. Existing source-aware payout release protections are retained.
