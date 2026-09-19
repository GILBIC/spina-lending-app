# Priority 9 — staff Android completion

This batch completes the remaining Management, Employee and Collector Android workflows backed by existing protected APIs. It follows the frozen Management roadmap in [Master296's Management freeze](https://github.com/GILBIC/spina-lending-app/issues/296#issuecomment-5627859431), after Priority8 / PR424. It does not reorder the roadmap.

## Acceptance scope

| Bucket | Delivered behavior |
| --- | --- |
| P9-1 Office lifecycle | Shared authorized office intake, requirements, CIF drafts/corrections/privacy and provider-baseline evidence, exact-version review confirmations, loan application entry/review, Management first-loan decisions, immutable packet download, signing/cash evidence, release and separate credential handoff. |
| P9-2 Staff operations | Area tree maintenance, server impact previews, collector assignment, borrower area transfers, Management past-due reason report and managed access for existing active unlinked borrowers. |
| P9-3 Management review | Payment-proof queue/history/file retrieval and immutable review decisions; decimal journal entry and recovery after an uncertain creation/reversal. |
| P9-4 Collector | Terminal access denial clears route caches and live actions; authoritative penalty/payoff facts retain exact decimal text; Notifications and Connectivity are available from More. |
| P9-5 Shared access | Permission-scoped Management/Employee navigation, Employee support, supported support decisions only, and guarded Client password reset with masked credentials. |
| P9-6 Verification | Meaningful regression coverage for contracts, denials, exact money, uncertain results and navigation; combined Flutter analysis/tests, Android build, independent review and saved CI evidence. |

The PR and continuation checkpoint record the actual verification results. This document defines scope, not a claim that an uncompleted CI run has passed.

## Authority and recovery

- All mutations use the same authenticated, device-bound backend as Web. Role/permission launchers are repeated at protected boundaries; the server remains authoritative.
- Office confirmations bind the exact stored version/context. CIF/application review, borrower signatures and cash receipt are separate evidence events. Provider baseline recording is not a face-recognition provider integration.
- Staff monetary data stays decimal text. The app does not compute a substitute payoff, journal rounding adjustment or loan allocation.
- Protected files use authenticated retrieval. Supplied document hashes and evidence identity are checked before the user saves a file.
- No new offline write queue or background automatic retry is introduced. Supported idempotent operations retain their original coordinates after an uncertain result. Other writes require authoritative reconciliation and a fresh explicit action.
- Uploaded payment evidence and Management evidence-review decisions do not post a collection, prove GCash settlement or reduce a borrower balance.
- Client account creation is Management-only with account.manage. Client password reset is separately available to authorized Employee/Management with client.credential.manage. One-time passwords remain in memory and can be cleared; readable passwords are not cached.
- Area moves and borrower transfers show server previews. Final decisions and effective collection dates remain server-controlled.

## Deliberate boundaries

The approved four-role design permits HR, payroll, attendance, leave and task placeholders to remain honestly unavailable until real APIs and policies exist. Employee accounting does not bypass Management-only financial APIs. No HR engine, new accounting policy, new lending rule, native iOS build, live GCash integration or notification-reading automation is added.

This is source implementation and automated verification. Actual Android device UAT for camera/gallery, authenticated save dialogs, background/resume behavior and network loss remains a release gate. Production privacy/legal templates, provider configuration, persistent private storage and deployment authorization remain separate. This batch adds no database migration and performs no production account, database, customer, cash or provider operation.

## Verification entry points

Run from gilbic_mobile:

- flutter analyze
- flutter test --reporter expanded
- SPINA CI creates a clean temporary Android host and runs flutter build apk --debug --target-platform android-arm64,android-x64 --no-pub. This produces a device-test artifact, not a signed production release.

Focused regressions include office_* tests; staff_operations_* tests; management_payment_proofs_test; general_journal_exact_money_test; management_general_journal_page_test; collector_android_completion_test; client_password_reset_safety_test; Management/Employee navigation, support and review-inventory tests.

The backend routes were compared directly with their current request/response contracts. No backend implementation or schema is changed in this batch; existing CI retains backend, Portal and disposable PostgreSQL regression lanes.
