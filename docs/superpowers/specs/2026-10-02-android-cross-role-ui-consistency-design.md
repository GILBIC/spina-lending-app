# SPINA Android Cross-Role UI Consistency — Design and Acceptance

Date: 2 October 2026 (Asia/Manila)

## Status and authority

**Planning only.** The owner requested “Plan everything and create a pr” after the Android consistency review. This document and its implementation checklist are a separate Android handoff for owner-started Codex execution, consistent with the preceding handoffs. They do not implement fixes, run an agent automatically, approve a release, or authorize production operations. Keep the PR Draft/open/unmerged.

Reviewed baseline: `GILBIC/spina-lending-app`, main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013` after #484. Planning branch: `plan/android-cross-role-ui-consistency-20261002`. Reconcile live main/open PRs before execution; do not assume this baseline remains latest.

Authorities:
- [Android cross-role review](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5944212677), including its evidence limits.
- [Frozen Master #296](https://github.com/GILBIC/spina-lending-app/issues/296) and later approved scope comments; do not rewrite or check owner-acceptance boxes.
- [Approved CA1 foundation #369](https://github.com/GILBIC/spina-lending-app/pull/369) and [Management restoration #464](https://github.com/GILBIC/spina-lending-app/pull/464).
- [Notion Current Project State](https://www.notion.so/3cd5ade7bef48106b2c2ff97182001dd) and Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`. Compare dated evidence: semantic search can return superseded decisions.
- Separate Web PRs #485–#488; they are not Android implementations and are not edited by this handoff.

The prior review inspected Flutter source/tests and ran bounded static calculations only. It did not run Flutter tests, an APK, an emulator, TalkBack, or native screenshots. Dense-layout findings are testable risks, not reproduced overflow. The conversation ZIP is optional reference, not assumed present in Codex. Reproduce from current source.

## Intent and selected approach

Make Management, Employee, Collector and Client feel like one SPINA product in status meaning, recovery, typography, secondary actions and records, while retaining different primary jobs. Reuse `SpinaTheme.light`, `WorkspaceAccountMenu`, existing repositories and protected workflows. Apply small presentation helpers only where multiple real consumers need them; do not introduce another router, state framework, design-token framework or payroll system.

A palette-only pass would leave misleading statuses/recovery. Replacing all four homes with identical navigation would discard approved workflows and the Management restoration. The selected approach is targeted consistency plus native evidence: status/recovery first, adaptive readability next, secondary labels/formatting/details, then cross-role verification.

## Permanent boundaries

- Preserve Material 3, the approved pink/white visual identity, existing typography/component system, 52-high standard filled/outlined buttons and at least 48-by-48 interactive targets. Do not reduce OS text scaling to fit content.
- Preserve restored Management grouping/layout intent from #464 and one Management workspace without a role switch. Keep Employee/Collector combined-workspace routing and original authenticated permissions unchanged.
- Preserve Collector route-first entry, exact loan IDs/Regular–7x7 separation, approved one-tap and atomic combined-payment behavior. No blanket new confirmation screens or changed payment tap contract for visual uniformity.
- Financial writes remain online-only. Preserve exact request money/IDs/sequences/hashes, pending-command recovery, duplicate/uncertain locks, readback, independent approval, custody, borrower-only signing/cash confirmation and server object permissions.
- Android protected attendance capture/outbox is intentionally different. Preserve encrypted actor/device binding, capture/server times, accepted/pending/review states and safe sync. It is not a financial-write outbox or proof of payroll payment.
- Presentation helpers never calculate payoff, interest, penalty, allocation, tax, payroll, eligibility or global totals, and never supply display-formatted values to write builders. Do not change numeric model types or backend contracts as a side effect.
- No new backend endpoint, role grant, schema, dependency/SDK upgrade, global store, persisted draft/cache, package ID, signing configuration or app-version bump. Do not rename `gilbic_mobile`, API identifiers, storage keys, audit enums or historical documents when cleaning visible branding.
- Preserve session/identity/device/permission cleanup, private image/file lifetimes, picker recovery, one-time credentials and exact mirror/capture boundaries. No new capture-eligible page. Synthetic emulator screenshots for review are allowed; live screen sharing or production screenshots are not.
- This work is Android-focused Flutter UI, not Web/iOS/Desktop redesign or whole-product feature parity. Shared Dart code must keep other platforms compiling and their established platform behavior; no new native-iOS deliverable is implied.
- No automatic agent invocation, mark-ready, merge, auto-merge, release tag, delivery/deployment, migration, production credential use, real payment/approval/attendance/photo/signature/cash receipt, or owner-acceptance changes. Existing CI may build its internal debug artifact; that is not an install/delivery authorization.

## Coverage: all review findings

| Review ID | Required outcome | Implementation task |
| --- | --- | --- |
| A1 | Truthful channel indication and coherent status presentation | 1 |
| A2 | Correct failure actions, visible partial schedule errors and safe recovery | 2 |
| A3 | Native small-screen/large-text readability and touch targets | 3 |
| A4 | Consistent secondary labels/access presentation without identical homes | 4 |
| A5 | SPINA visible copy and exact money/date display conventions | 5 |
| A6 | Curated Employee record summary with complete detail/history | 6 |
| A7 | Device-saved attendance versus online-only finance explained accurately | 7 |
| A8 | Production-theme fixtures, native matrix, accessibility and exact-head evidence | 0, 8, 9 |

## A1 — Truthful status meaning

Remove `_statusChips` channel inference from `status`, `note` and `todayNote` text in `collector_client_ledger.dart`. “Not paid through GCash”, “Do not use GCash” and “GCash tomorrow” must never imply a verified payment channel. Baseline route data does not establish a trusted channel through this substring. Default implementation is a neutral **Note** indicator when a note exists, with its text available in details. Only adopt a channel field after verifying its existing producer, exact transaction scope and meaning; never add a fabricated field or treat proof/checkout status as an official payment.

Use a small shared status widget with explicit label, icon/semantics and tone, not a universal financial-status parser. Preserve role/domain distinctions: Payment recorded is not Cash received; Payroll approved is not Payroll paid; Saved on device is not Server accepted. Unknown values are informational/unavailable, never success. Existing state predicates remain authoritative; any ambiguity in a predicate such as lock-versus-custody is recorded separately rather than silently rewritten.

Use existing success/warning/error/neutral theme colors with a tested foreground/background pair. Text and icon must carry the distinction without color alone. Collector status text uses the production labelMedium style, not an explicit size 9. Expand/wrap instead of shrink. Keep full labels accessible through semantics and details. Status decoration must not create an extra financial tap target.

Apply the component to the reviewed Collector pills and corresponding status displays in shared Employee records and Client loan cards; audit Management queue/status consumers and use it where semantically equivalent. Do not repaint every chip or chart blindly.

## A2 — Correct recovery and partial-data presentation

Adopt a shared read-error presentation contract, not shared mutation retry logic:

| Condition | Presentation/action |
| --- | --- |
| Initial/transient network read failure | Clear unavailable message and **Retry** for that read |
| Refresh failure after a valid snapshot | Last successful snapshot explicitly marked not refreshed; scoped Retry |
| 401/session expired | **Sign in again**, calling the existing supplied session/sign-out flow; no same-token reload loop |
| 403/device or permission denial | Clear affected private data; **Access unavailable** guidance, Back/Account or explicit sign-in recovery; no retry implying a grant |
| Update-required response | Preserve the existing mandatory-update flow; no download URL or capability invented |
| Successful empty result | Explain genuinely empty records; never use a failed request's fallback list |
| Uncertain financial result | Existing blocked reconciliation, not generic Retry or success |

Client home must retain independent load state per active 7x7 loan (`loading`, `ready`, `unavailable`) rather than silently dropping a failed schedule. Render verified portfolio data while schedule requests complete, and label each missing schedule/payoff section **Schedule/payoff information unavailable** with **Retry schedule**. A successful retry updates only the same loan's authoritative data. Maintain exact payoff/projected-versus-assessed penalty/Management-review distinctions already in the native model. Do not invent today's installment or derive payoff from balance.

Use mount/request generations and current session/loan membership to ignore stale responses. Removed loans, logout, a different actor/device or revoked access must not regain details from a late response. Repeated activation deduplicates a pending read. A 401/403 nested schedule error must not be swallowed as ordinary optional absence. Preserve the original callback/repository dependencies and do not clear unrelated pending financial attempts to make a fresh screen appear.

Roll the read-error wording/action contract through the four reviewed home/entry surfaces and shared notifications/account/employee records where applicable. Do not remove Collector's existing domain-specific failure guidance. Unknown backend text must not expose secrets or implementation traces.

## A3 — Native readability without redesign

The fixed 52/44/74-wide Collector columns, 48-high two-line Pay controls, Management 104/92-high cards/four attention columns and Client trailing amount row are baseline risks. First reproduce with the production theme; do not declare them broken solely from source dimensions.

On normal-size/default-text screens retain the recognizable approved layout where it fits. With narrow width, long values or enlarged text, allow natural height, wrapping/stacked amount rows and fewer grid columns. Keep Collector identity, separate loan types, amount and action together. A normal one-line truncated name may remain only when exact identity and full name are reachable; amounts and consequential-action labels may not be ellipsized, rounded, abbreviated to K/M, clipped or reduced by scaleDown to hide the problem.

Management KPI cards become minimum-height/natural-height, with an adaptive column count; attention items wrap their labels rather than relying on tiny text/tooltips. Preserve section ordering and the restored normal design. Client amount rows stack when a full value cannot fit. Collector financial controls remain at least 48 high/wide and can grow for two lines; standard noncompact buttons retain the 52 minimum.

Test keyboard-open forms, bottom safe areas, Android Back, TalkBack reading order, visible focus, long references, landscape and a tablet width. Keep existing content reachable without horizontal whole-screen scrolling. Do not suppress RenderFlex exceptions, cap TextScaler, enlarge the test viewport or trim fixtures to obtain green results.

## A4 — Secondary navigation and permission presentation

Keep primary navigation role-specific: Management grouped oversight; Employee work/pay; Collector Route/Master review/Remit/More; Client personal loans/actions. Collector pushes a page from bottom navigation; a constant selectedIndex alone is not a diagnosed bug and does not justify replacing its navigation system.

Canonical shared labels are **Profile & security**, **Notifications**, **Offline & sync**, **Sign out**; the existing shared menu tooltip is **Account & tools**. Reuse existing destination widgets and keys. Management retains its restored top-bar Sign out and existing module access; do not relocate or replace the dashboard as a consistency shortcut. Employee and Client retain their account menu; Client's notification bell is an intentional shortcut. Collector keeps More, but uses the same secondary labels. Optional duplicate links may remain when they are documented quick access, not duplicate implementations.

Hide optional business-tool entries when the user lacks their current permission, matching Management/Employee behavior. Preserve stable Collector primary destinations; an unavailable fixed destination has a visible disabled state and an accessible reason, not an enabled workflow which only denies after tapping. Recheck permission immediately before navigation and keep server authorization. Required data/setup missing is different from lack of permission. Personal Account/Notifications remain reachable through the existing allowed fallback.

Navigation never initiates a payment, accepts custody, clears pending attempts or expands mirror eligibility. Preserve worker-switch state/session isolation and privacy hooks before leaving a sensitive surface.

## A5 — Shared visible copy, money and dates

Replace old **Gilbic** only in app-authored visible messages/tooltips in the reviewed Android surfaces. Do not replace user notes, received references, package names, endpoint keys, persistence identifiers or archived evidence. Keep a short exception inventory for any user-visible legacy identifier whose display is required.

Money contract: full display uses the peso sign and digit grouping, at least two fractional digits, and preserves any additional supplied precision without rounding. Examples: `'12345.60'` -> `₱12,345.60`, `'-50.00'` -> `-₱50.00`, `'0'` -> `₱0.00`, `'1.2345'` -> `₱1.2345`. Missing/invalid authoritative money is **Unavailable**, not zero. Use the existing exact Client formatter as the implementation basis and preserve its public wrapper. Never parse exact decimal strings through double.

An intentional Collector compact variant may omit an all-zero fractional part (`'1200.00'` -> `₱1,200`), but never remove nonzero cents (`'1200.50'` -> `₱1,200.50`), abbreviate magnitude, or supply a write value. Announce the full amount in semantics/confirmation. Where a legacy UI model is numeric, reuse verified exact-text accessors if available; otherwise use its existing validated display conversion and record its precision limits. Do not manufacture precision or refactor allocation/model arithmetic in this UI PR.

Calendar dates use `YYYY-MM-DD` consistently and preserve the server's calendar fields, without timezone conversion. Instants use the existing Manila business-time helpers and `YYYY-MM-DD HH:mm`; label the section **Times shown in Asia/Manila** where ambiguity matters. Stored/transmitted UTC and date-picker request semantics remain unchanged. A missing date is **Not recorded**; a malformed date is **Unavailable**. Do not run date-only values through an instant-to-Manila conversion.

Apply these helpers to the reviewed four homes, Collector cash/ledger details, Client loan/payment/schedule summaries and Employee record summaries. Inventory remaining divergent presentation in directly reachable screens; use the same contract for bounded display-only changes, otherwise retain a named follow-up. Do not claim whole-app migration from four screenshots.

## A6 — Employee summary, details and history

Reuse `EmployeeOperationsPage` across Employee, Collector and Management; do not create a second HR/payroll store or merge these roles' authority. Add curated read-only summaries for Attendance, Requests, Tasks, Advances, Payroll, Shortages and Accounting preparation. Show employee/record identity, meaningful date/period, current status, supplied amount and permitted next action first. Missing setup remains incomplete, not zero pay.

Keep all currently authorized returned facts and record/version/source IDs reachable under **Details** and existing **Record history**. Preserve server order, unknown fields in details, sensitive-field exclusions and exact IDs; never reveal excluded metadata just to make the list complete. Unknown record types fall back to the safe existing detail renderer. Payroll net/gross/deductions/paid/outstanding values are only shown where actually returned, not derived. An approved/unpaid payroll record must not look like proof of payment.

The same permitted action calls the same command/form with unchanged record ID/version/request recovery. Hiding a detail panel must not dispose an unfinished command or selected evidence. Audit visibility, owner-only actions and independent approvals remain unchanged. This is hierarchy work, not new printing, payslip generation, self-approval or broad reports.

## A7 — Offline, in-progress and privacy consistency

Use distinct explanations for **Saved on this device — awaiting server sync**, **Received by server**, **Needs review**, **Read-only saved route**, and **Online connection required for financial actions**, mapped only to actual existing states. Do not relabel local attendance as server-approved or payroll-paid. Existing safe attendance sync can continue automatically under its established service policy; this does not permit automatic financial retries.

No navigation, read Retry, view rebuild or theme change may clear an uncertain payment/custody/posting lock, replace its request identity, or transfer queued attendance to another account. Verify offline-before-open, disconnect-during-submit, expiry, same-actor token rotation, account/device change, permission revocation and app restart with existing protected stores/fakes. Clear private views on denied scope while preserving pending evidence only according to its established owner/device policy.

Preserve current mirroring exclusions and picker/file cleanup. New semantic labels must describe visible authorized information, not hidden passwords/IDs/photo content. Synthetic screenshot harnesses are test-only; no route added to the signed-in app, public preview menu, real capture session or external analytics.

## A8 — Required native acceptance, not Web evidence

Create shared fixtures using the actual `SpinaTheme.light` and Android target platform. Set MediaQuery/TextScaler inside MaterialApp's builder or below its generated MediaQuery; assert the observed scale inside the actual target widget so a surrounding test wrapper cannot silently be overridden. Reuse fake repositories/device identity/storage, block unexpected network and keep real accounts/private signing keys out of tests.

Mandatory home matrix: 4 roles x widths **320, 360, 412** x text scales **1.0, 1.3, 2.0** = **36 named configurations**. Use heights **640, 640, 915** respectively and devicePixelRatio 1 for deterministic widget captures. Capture the real widgets, inspect complete scrollable content, and record exact source/tool versions. Test a real Android device/emulator at the OS maximum font setting too: linear widget scales alone do not prove Android nonlinear scaling.

Add representative record/form/state checks: Collector single and combined payment/short/extra/ADV/correction/remittance; Client missing/recovered schedule, denied/session-expired, long loan/payment amounts; Employee attendance queue/leave draft/advance/payroll/history; Management overview/permission-limited account/financial confirmation. Include keyboard inset 220 at small width, landscape, tablet, reduced motion, Back, long labels, duplicate names, explicit zeros and unknown states.

Automated semantic checks use Flutter's `androidTapTargetGuideline`, `labeledTapTargetGuideline` and `textContrastGuideline` on representative screens. Target 4.5:1 for ordinary text and at least 3:1 for large text, without treating three palette calculations as whole-app certification. Inspect status text/icons in grayscale. Actual TalkBack and Android Accessibility Scanner findings are a separate evidence gate, not implied by widget semantics or CI.

References checked for this plan: [Flutter accessibility testing](https://docs.flutter.dev/ui/accessibility/accessibility-testing), [UI design and styling](https://docs.flutter.dev/ui/accessibility/ui-design-and-styling), [Android nonlinear text scaling](https://docs.flutter.dev/release/breaking-changes/android-14-nonlinear-text-scaling-migration). Use the repository's pinned Flutter version; these references do not authorize upgrades.

Each product task has failing behavioral evidence before the fix, focused passing tests afterward, a reviewed commit and a checkpoint. Final analyze/test plus existing exact-head CI are required. Reuse current generated Android-host/build/verification tooling; do not invent an Android directory or duplicate workflows. CI's internal debug APK is not a released, installed or owner-signed build. Emulator runs use an isolated synthetic fixture host; physical installation, production connection and signed delivery require separate owner authorization.

Finish with an A1–A8 evidence ledger, the 36 matrix results, actual versus blocked native/TalkBack checks, source SHA, commands, build identity where available and synchronized GitHub/Notion/Create State. If tools are unavailable, retain the fixture/tests and explicit blocked status; do not mark visual acceptance or Master CA complete. Keep Draft/open/unmerged.

Implementation: [2026-10-02-android-cross-role-ui-consistency.md](../plans/2026-10-02-android-cross-role-ui-consistency.md).
