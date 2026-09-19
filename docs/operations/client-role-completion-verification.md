# Priority 8 Client Role Completion — continuation ledger

Date: 2026-09-19
Scope: existing approved seven-bucket plan `docs/superpowers/plans/2026-09-12-priority-8-client-role-audit.md`; draft PR424.

## Starting evidence

User instructed `next` after PR420 merged. Main `faa885706243ad50a77c4d4d1b3172f2c9df2884`; previous P8 head `aab3ee666bb4e0c2c21de148ee48c99935ba74d0`. P8-1,2,5,6 and bounded7 previously accepted, P8-3 partial and4 outstanding. Current reporting71% (five complete of seven; partial bucket receives no credit). All seven require final combined-head validation before100%.

## Integration

Resolved only three text conflicts: preserve exact decimal strings and stored first payment date, preserve removal of inferred progress and first-payment assertions, union Client and office precache assets. Portal530/530, Client loan+statement API8/8, Flutter merged loan/date tests4/4 passed. Initial local runner mistakes (two nonexistent Flutter test filenames, missing current-worktree PYTHONPATH) were corrected before these results; not product failures.

## Remaining batch

- P8-3: borrower's immutable released packet retrieval, current authoritative statement/payment-record PDF copies, Web/Android access.
- P8-4: protected versioned payment evidence upload/correction, status/reasons/history, private attachment retrieval, Management review, Web/Android access.
- Fresh integrated acceptance: relevant regression tests, PostgreSQL ownership/retry/concurrency, all portal+Flutter checks, CI, browser flow, final review.

## Decisions

Ruling: historical finalized packets reuse exact issued bytes and release binding; no re-render of historical contracts. Paid/closed loans retain access, unreleased/unowned loans do not.

Ruling: no historical receipt/statement PDF authority exists. Provide clearly labelled server-generated record copies from existing authoritative read models with generated time/current void/correction state. These do not issue a receipt number, regenerate a legal original, or constitute a new tax invoice. The original official receipt artifact remains unavailable where no original was issued. Cost if wrong: export labels/format need owner adjustment; source ledger remains unchanged.

Ruling: payment-proof review is evidence review only, with immutable versions/reasons and guarded retries. It never verifies provider settlement, posts collections or reduces balances. No missing payment confirmation policy is inferred.

## Boundaries

Keep PR draft pending separate merge authorization. No production database/Auth/customer/cash/provider change, activation or deployment. Legal/privacy template production gates remain. Full remaining batch is executed continuously; user Red/Green is optional feedback, not a step gate. Preserve frozen Master296.

## Batch verification checkpoint

- Reconciliation committed as `dfd732e1ea44151baa3f78b0175b871ec2af9dc8`.
- Combined disposable PostgreSQL: **510 passed**, including all16 new historical-document cases and35 new evidence cases. Database `spina_onboarding_4c218080f1ca` was created and dropped. Proof tests cover exact retries, concurrent request/review conflicts, immutable versions/reasons, wrong owners/devices/roles, original bytes, and unchanged financial/Auth records.
- Document/API/read-model regression group:68 passed; proof API plus existing payment timeline:43 passed. A final combined run includes those and a real CORS preflight regression.
- Web browser at1280px and390px: complete Client upload → Management correction → Client revised upload → Management evidence review; both original versions and review history preserved; statement/signed-scan/evidence downloads; zero console errors and zero financial writes. Actual phone-width overflow was reproduced, then fixed by bounded grid minimum widths.
- Six pages of synthetic statement/voided payment-copy PDFs passed exact text/money/non-ASCII, page bounds and visual checks; original data and literal markup remain literal. Continued pages retain receipt identity and void status. QA report/artifacts are in task-owned `../p8-document-samples/`.
- Independent backend reviews found no blockers. Independent Web review found two important issues: unreadable successful mutation responses could clear retry identity, and invalid2xx blob content could be saved as a document. Reproduction tests were Red, fixes Green; all11 focused Web document/evidence tests now pass. Android already retained malformed responses and was additionally hardened for wrong response identity.
- Final integration reviewer found no additional Important/Critical issues across backend ↔ Web/Android, permissions, routes, CORS, SQL/CI wiring and original-versus-copy semantics.

Ruling: private free-form proof notes travel as strict base64 UTF-8 in `X-Proof-Note`, never in URL query parameters; this is encoding, not encryption. Standard authenticated HTTPS remains required. IDs/version guards remain query parameters. This avoids putting notes in ordinary request-line logs.

Native Android saving uses file_saver0.4.0 with authenticated bytes and the system save dialog; no bearer URL is handed off. Android accepts photos using the existing camera/gallery picker; PDF proof files can be submitted through Web. Real-device save-dialog acceptance remains part of device UAT; widget/repository analysis/tests and CI APK packaging validate the implementation.

Candidate-publication checkpoint: acceptance remains71% until combined final CI succeeds. No new bucket is accepted merely because implementation exists. The final accepted head and CI runs are recorded on PR424, Notion Current Project State and the local handoff.

Final local combined API run:109 passed (two existing framework deprecation warnings); all new backend files pass Ruff. Portal build:544 tests passed. Browser flow was rerun after the review fixes and passed at1280px and390px,31 protected requests per viewport,2 versions/2 review events,3 download actions and no financial writes or console errors. Disposable cluster inspection found zero leftover task databases or other client sessions; the owned PostgreSQL and static preview processes were stopped.

Final full Flutter run after response-identity/retry fixes:580 tests passed; analysis reported no issues. This supersedes the earlier576-test checkpoint and isolated follow-up runs.
