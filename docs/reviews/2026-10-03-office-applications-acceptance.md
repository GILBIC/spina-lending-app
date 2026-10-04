# Office applications implementation evidence

Implementation authorized by the owner on 4 October 2026: “Go do it.” The visible recent-intake list is required so staff can recognize and reopen saved cases without remembering reference numbers. This record tracks PR497; it is not production or financial-operation approval.

## Baseline

- Existing planning/list clarification: b5971866ab3af7004885fb281f0c3890d3e32d91.
- Deployed main preserved: b5d6962f9baf3edc7cf471e1879151d63220cba5.
- Conflict-free integration baseline: 88553588e977192b98b9083741c6d772b2be1d13.
- `npm test`: 1,637 passed, zero failures/skips. The log contains three pre-existing `MaxListenersExceededWarning` entries (one visibilitychange and two focusin listener warnings); the Task 1 full run retains the same counts.
- `node tools/build_portal.mjs`: passed.
- Actual built Management Office panel captured at 1440/1280/1024/997/768/390/320 CSS-pixel widths (height 857), with a synthetic in-memory API, zero writes and no browser errors. No page overflow in this isolated panel; entry height grows from about 308px at 997 to 697px at 320. This baseline panel capture does not establish full-shell, improved-layout or authenticated-production acceptance.
- Two new actual intake-module regressions initially failed as expected: editing lookup removed the original unfinished form; starting a new intake retained the old saved reference. Task 1 repaired and verified both; final integrated evidence remains pending.

Local working evidence is retained in `.superpowers/sdd/2026-10-03-office-applications-workflow/`: baseline-portal.log, baseline-build.log, baseline-office-browser.json, baseline-office-997.png and task1-red.log. Logs and screenshots contain synthetic data only.

## Requirement coverage

| Requirement | Plan tasks | Current evidence |
| --- | --- | --- |
| New/Continue entry and list visible on opening Office | 2, 5, 7 | Pending |
| Verified case identity and retained unfinished work | 1–4 | Tasks 1–3 approved through de47ae74: all four owners, real Files and all-stage New covered. Global write exclusion, full privacy lifecycle and explicit uncertainty recovery remain Task 4 |
| Truthful case/stage status and explicit saved application | 3, 7 | Task 3 approved: verified version-aware banner and protected explicit application selection. Visible saved-application picker remains Task 7 |
| Protected paginated reads, minimal rows and private logging | 6 | 7ca37271: 935 Office database tests and 77 route/auth/logging regressions passed. Review fixes at 2e3f456b: 60 cursor tests and 184 focused PostgreSQL/API tests passed; independent scoped re-review approved |
| Management/Employee layouts, keyboard, zoom and PWA | 5, 8 | Full built shell and role-navigation baseline at seven widths per role, zero errors/writes/overflow; improved-layout, keyboard, zoom and PWA acceptance pending |
| Full integration, review and exact-head CI | 8–9 | Pending |

## Boundaries

Task 3 adopted application/release owner handles and a shared truthful banner at 515f151f. Its 513 relevant tests and built Management/Employee browser flows passed; real CIF/application Files survived stage changes and cancelled New, with zero implicit writes. Independent review then reproduced two version defects: a same-reference newer version failed to reach discard consent, and older cancelled first-loan packets blocked current-version reads. Commit de47ae74 fixed both with seven product RED cases and 266 covering tests passing; scoped re-review approved. Historical packets keep their own version identity, while only exact matching packets supply current-version status. The built browser evidence predates this fix; final rebuilt whole-flow acceptance remains Task 8. The earlier relevant run retained one pre-existing focusin listener warning; the selected fix run had none.

Task 2 adopts callable dirty/revision/write/uncertain handles for CIF correction, signing, evidence and privacy children. Ordinary search edits, failed candidates, cancellation and same-case navigation retain actual File/control identity. The original scoped implementation passed 484 Office/role/CIF/Collector tests. Review then found premature destruction during correction lookup and repeat first-draft creation after acknowledged-save/read404/409; fe339106 fixes both, with 193 covering tests passing and scoped re-review approved. Cancellation of intake Close now retains initiating-control focus. Full all-stage New and legacy uncertainty/Refresh reconciliation remain explicit Tasks 3–4 dependencies.

Task 1 uses one mount-owned coordinator shared by both Office roles. Intake lookup edits retain live controls, New detaches old identity, candidate failures/cancellation preserve authorized work, and verified-save/read-failure recovery retains its known reference. A narrowly added application callback tags generated references as unsaved. Independent review required exact application-reference matching and a recoverable rejected/stale producer state; both were fixed and re-reviewed. The full portal run passed 1,653 tests before that bounded fix; its covering Office/role run passed 410 afterward. This is foundation evidence, not final all-stage or browser acceptance.

Independent Task 6 review found malformed JSON cursor types could return 500, and a duplicated persisted access check. Commit 2e3f456b validates cursor field types before conversion and shares the existing Office/Collector reader authority. The malformed-type test run first reproduced 20 failures. All 60 cursor cases then passed, followed by 184 actual PostgreSQL/API cases with zero skips (one unchanged query-plan test deselected). Scoped re-review confirmed both findings addressed without new breakage. The full 935-case result above predates this bounded fix; final integrated validation remains pending.

The additional full-shell baseline uses actual built index markup, role mounts and navigation, with a synthetic session/API. At 320 pixels, the Management Office panel starts at 466.55 pixels and is 697.28 pixels high, placing New intake below the initial 857-pixel viewport. Representative Management 997/320 and Employee 320 captures were visually inspected. This explains a concrete entry-layout problem but does not establish improved-layout or authenticated production acceptance.

Task 6 used a new synthetic PostgreSQL 18 cluster on loopback port 56426. The existing Office validation runner applied the schema through migration 0139 to a disposable database and passed 935 tests with no skips. Both new test files are selected by that runner. Its databases were dropped and the owned cluster stopped. No schema migration was added. Focused query plans covered 10,001 intakes, 1,000 application headers and 10,000 versions; they did not justify a new index.

The broad backend test attempt was stopped at 11% because the host had only 431 MiB of available RAM while two suites ran. It is not a passing result; the full backend remains a final integration/CI requirement. The passing Office run retained one pre-existing Starlette/TestClient dependency warning.

Checked-in Uvicorn and Caddy deployment configuration does not log finder queries. A preserved operator-owned proxy configuration is outside this source verification and must also omit or redact sensitive request queries before release.

No live customer data, database migration, provider operation, financial write, feature activation or deployment is part of this implementation verification. PR496/498 and frozen Master issue296 remain separately owned. Existing source-aware payout release protections are retained.
