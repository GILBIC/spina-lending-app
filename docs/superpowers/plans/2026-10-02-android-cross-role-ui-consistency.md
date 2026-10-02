# SPINA Android Cross-Role UI Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Preserve owner-started Codex execution; this handoff does not launch an agent. One integration owner edits shared theme/widgets and overlapping role files.

**Goal:** Resolve the Android consistency review across Management, Employee, Collector and Client without replacing approved layouts or altering financial behavior.

**Architecture:** Reuse the existing Flutter theme, role routing, shared account/notification screens and Employee Operations. Add only small presentation helpers for semantic statuses, read recovery, exact display and curated record summaries. Existing repositories, commands, pending identities, permission checks and storage remain authoritative.

**Tech Stack:** Existing pinned Flutter/Dart, Material 3, flutter_test and Android generated-host tooling. Baseline pubspec: Dart `>=3.10.0 <4.0.0`, app `0.5.0+7`; these are source facts, not the installed app version. Use the current CI pin and lockfile; no upgrades or new runtime packages.

**Spec:** [2026-10-02-android-cross-role-ui-consistency-design.md](../specs/2026-10-02-android-cross-role-ui-consistency-design.md).

**Status:** Planning only; all Tasks 0–9 pending. Reviewed main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`. Branch `plan/android-cross-role-ui-consistency-20261002`. Previous evidence was source/static review, not Flutter/emulator acceptance. The original review is [issue448 comment5944212677](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5944212677).

## Global constraints

- Preserve approved Material3 pink/white theme, 52-high standard filled/outlined buttons, at least48x48 interactive targets and unrestricted OS text scaling.
- Preserve #464 Management restoration, one Management workspace, worker routing, Collector route-first/one-tap/atomic payment behavior and every original permission/object boundary.
- Financial writes remain online-only. Keep exact request money, UUIDs/sequences/digests, stale-version checks, uncertain-result locks, explicit sensitive confirmations and independent borrower/recipient actions.
- Preserve protected offline attendance and its actor/device-bound store; device capture is not server acceptance or payroll payment. No financial outbox or automatic financial retry.
- Formatting/status widgets never feed write builders, calculate financial facts, alter money model types or reinterpret policy. Retain data/record history and protected exclusions.
- No new endpoint/schema/grant/dependency/SDK/global-store/persistence/package-ID/version/signing change, Web redesign, native-iOS rollout or duplicate employee system.
- Preserve credential/file/image/recovery lifetimes, denied-data cleanup and mirror/capture exclusions. Test screenshots of synthetic UI are allowed; production screenshots and live screen sharing are not.
- Keep PR Draft/open/unmerged and automatic merge off. No mark-ready/merge/tag/delivery/deploy/migration/production credentials or operations/Master acceptance changes. Existing automatic CI builds are not owner installation/release approval.
- Reuse live GitHub/Notion/Create State before asking for old decisions. After meaningful progress record exact SHA, tests, evidence, limitations and next action. Disclose connector failure instead of claiming sync.

## Review focus

1. A note that names a payment method, a pending state or an unknown token must not become verified payment/custody evidence — Task1.
2. A schedule401/403, per-loan failure, two overlapping refreshes or account switch must not hide a failure or reveal stale private data — Task2.
3. Long exact amounts, names, text scales1.0/1.3/2.0 and keyboard/safe-area constraints must not be solved by shrinking or clipping — Tasks3/8.
4. Navigation or record presentation must not reset pending commands, lose a draft, duplicate an action or extend a grant — Tasks4/6/7.
5. Date-only versus instant values, extra decimal precision, numeric legacy sources and offline attendance must retain their actual meaning — Tasks5/7.

## File map

All paths below are repository-relative. For task brevity, **src/** means `gilbic_mobile/lib/src/`; **test/** means `gilbic_mobile/test/`.

Existing primary files:
- `src/theme/spina_theme.dart`: preserve theme; only bounded reusable semantic/spacing adjustments.
- `src/features/shared/daily_workspace_widgets.dart`: existing WorkspaceBody/WorkspaceAccountMenu; add stateless read notice and common labels here.
- `src/features/dashboard/enhanced_role_dashboard.dart`: routing regression surface, not redesign target.
- `src/features/management/management_dashboard.dart`: restore-compatible adaptive overview and display.
- `src/features/collector/collector_client_ledger.dart`, `collector_field_home_page.dart`, `collector_cash_status_card.dart`, `collector_failure_guidance.dart`, `collector_route_page.dart`: status, compact layout/copy and existing guarded guidance.
- `src/features/client/client_dashboard.dart`: action-correct errors and per-loan schedule loading; bounded formatting in `client_loans_page.dart`, `client_payments_page.dart`, `client_schedule_page.dart`.
- `src/features/employee/employee_dashboard.dart`, `employee_operations_page.dart`, `employee_command_form.dart`: curated display/labels, command behavior unchanged.
- `src/features/notifications/notification_center_page.dart`, `activity_notifications_page.dart`, `remittance_notifications_page.dart`, and `src/features/offline/mobile_offline_policy_page.dart`: bounded wording/semantic verification, not new receipt routing.

Three proposed small production modules, only if no equivalent exists at execution:
- `src/features/shared/spina_status.dart`: label/icon/tone widget; no financial inference.
- `src/core/formatting/spina_display.dart`: exact display-only decimal/calendar/instant helpers, extracted from existing helpers without breaking compatibility.
- `src/features/employee/employee_record_presentation.dart`: safe summary/detail grouping for existing returned records; no model/store.

Read-only contracts/regression surfaces: `src/core/collector/collector_route.dart`, `core/loans/client_loan.dart`, `core/loans/client_schedule.dart`, `core/payments/request_money.dart`, `core/time/spina_business_time.dart`, `core/employee_operations/`, auth/session/mirror code, backend producers and existing tests. An import/wrapper extraction in `client_loan.dart` is allowed for display compatibility, not a change to parsing or write math.

Tests: add the named suites below under test/; reuse existing fakes. `test/support/android_role_fixture.dart` is test-only. Any synthetic emulator entrypoint lives under test support and is used only by a disposable host, never production app routes/menu. Do not add a shipping demo or new agent framework.

## Task 0 — Exact baseline, scope inventory and production-theme harness

**Files:** Read applicable AGENTS.md, spec, current main/PR diff, #296 with later scope comments, #369/#464, review448, Web485–488, `.github/workflows/spina-ci.yml`, pubspec/lock. Create `test/support/android_role_fixture.dart` and `test/android_role_fixture_test.dart` only if existing helpers cannot supply the same contract.

**Interface:** `pumpAndroidRoleFixture(WidgetTester tester, {required Widget home, required Size size, required TextScaler textScaler}) -> Future<void>`. It applies `SpinaTheme.light`, Android platform and the requested MediaQuery below MaterialApp's generated one, installs existing fake dependencies and restores all overrides/surface settings in teardown. It does not mask layout exceptions or use a live API.

- [ ] Fetch live main/open PRs/this branch plus Notion Current State and Create State. Work on this branch in an isolated Codex worktree; never reset other work or create a duplicate PR. Record overlap owner before shared Dart edits; Web branches remain separate.
- [ ] Inventory all four home entries and directly reachable shared Account/Notifications/Offline/Employee screens, with exact paths, permissions, current labels and fixture availability. Preserve restore/one-tap tests. Classify earlier findings as source-confirmed or unverified native risk, not all as runtime bugs.
- [ ] Verify available Flutter/Dart/emulator tools and current CI version. Reuse existing exact-head baseline evidence where valid; run missing baseline checks once. Unavailable tools stay explicit; do not claim an emulator from browser access.
- [ ] Test the fixture itself: a descendant sees Android platform, production primary color, target size and effective `textScaler.scale(10)` of10/13/20 respectively; an injected long-row overflow is actually reported, proving the harness does not suppress errors. Verify fake dependencies reject unexpected network.
- [ ] Run `cd gilbic_mobile && flutter test test/android_role_fixture_test.dart` when executable. Remove any deliberate failing probe after confirming harness detection. Commit the harness/inventory checkpoint only when it works; otherwise retain a blocked item without product fixes.

**Deliverable:** Auditable baseline and trustworthy native test harness. Native matrix completion is Task8, not implied here.

## Task 1 — Truthful channel and shared status presentation (A1)

**Files:** Create `src/features/shared/spina_status.dart`; edit Collector ledger, narrow Client status and Employee record status consumers. Add `test/android_status_consistency_test.dart`; retain `test/collector_client_ledger_test.dart`.

**Interfaces:** `enum SpinaStatusTone { success, attention, blocked, information }`; `SpinaStatusLabel({required String label, required SpinaStatusTone tone, IconData? icon, String? semanticLabel})`. The widget accepts already-decided domain status, never raw notes or permission rules. Collector's existing predicates produce presentations instead of only text; remove the textBlob/GCASH branch without altering payable/covered/custody predicates.

- [ ] Write `note_mentions_never_verify_gcash`, `unknown_status_is_not_success`, `domain_states_remain_distinct`, `status_label_respects_text_scaling`, and `status_decoration_does_not_submit`. Pin three note fixtures: Not paid through GCash; Do not use GCash; GCash tomorrow. Assert no GCASH badge and full note still reachable. Record unchanged selected loan IDs and write payloads.
- [ ] Run `flutter test test/android_status_consistency_test.dart` from gilbic_mobile; confirm missing behavior rather than a harness/import failure.
- [ ] Implement neutral Note and the labelMedium semantic status widget using existing palette. Keep literal meaning of Collected/Remitted/Unable/Lacking and record domain explanations; do not infer received custody from a color. Map payroll approved and attendance device-saved to their actual non-payment meaning. Retain unknown details safely. Verify any proposed channel field against producer; if absent, do not add it.
- [ ] Run new tests plus Collector ledger, Client dashboard and Employee Operations tests; assert no changed mutation calls, no smaller text and status understandable without color. Native visuals are captured later.
- [ ] Commit `fix(android): make status and payment-channel indicators truthful` with red/green evidence.

## Task 2 — Action-correct errors and independent per-loan recovery (A2)

**Files:** Edit Client dashboard and `daily_workspace_widgets.dart`; bounded read notices in Management/Employee/Collector entry surfaces. Add `test/android_read_recovery_test.dart`; keep existing `client_dashboard_test.dart`, `management_review_test.dart` and Collector failure tests identified in Task0.

**Interfaces:** Stateless `WorkspaceReadNotice({required String message, required String actionLabel, VoidCallback? onAction, bool stale = false})`; callers choose authority-specific actions. Internal Client `loadScheduleForLoan(String loanId)` tracks a generation/state per currently authorized loan; no global cache. Use existing `onSignOut` callback for the explicit Sign in again action, not automatic sign-out during a background refresh.

- [ ] Write `client_401_action_enters_session_recovery`, `client_403_clears_affected_data`, `schedule_failure_keeps_other_loans_and_shows_retry`, `schedule_retry_updates_exact_loan`, `old_read_cannot_overwrite_new_session`, `missing_payoff_never_becomes_zero`, and `read_retry_does_not_reset_financial_attempt`. Inject one ready loan, one deferred/failed7x7 read and a successful recovery; verify portfolio renders before the deferred schedule, only the failed loan retries, and Management-review-required remains distinct from payoff.
- [ ] Run `flutter test test/android_read_recovery_test.dart`; record the silent-schedule and wrong-action failures.
- [ ] Separate portfolio and schedule loads while retaining existing repositories and exact models. Provide Loading/Unavailable/Retry schedule per loan; no missing-read fallback to empty/zero. Use current-session/generation/loan membership guards; clear denied private content; preserve verified snapshot only for permissible transient read failure with stale wording. Align shared read notices without converting protected mutation recovery into generic Retry.
- [ ] Run focused and existing home/session/read suites. Verify 401 does not repeat a same-token GET, denied nested requests do not remain silent, repeated Retry deduplicates, disposal cannot reveal old records, and no extra POST occurs.
- [ ] Commit `fix(android): align read recovery and expose partial schedule failures`.

## Task 3 — Adaptive small-screen and large-text layouts (A3)

**Files:** Edit Management dashboard, Collector ledger/header/cash layout only where tested, Client summary amount rows and narrow shared widgets. Add `test/android_readability_test.dart`; retain Collector ledger, collection entry and Management review tests.

**Interfaces:** Use local LayoutBuilder plus TextScaler-aware natural constraints. Keep existing callbacks, keys, labels and data. No universal responsive framework. Expose full amount semantics independently of a permitted compact visual amount; no layout helper returns financial state.

- [ ] Add cases `collector_amounts_and_pay_label_remain_legible`, `management_metrics_grow_without_scale_down`, `client_long_amount_stacks`, `long_identity_has_reachable_full_detail`, `keyboard_keeps_action_reachable`, and `interactive_targets_at_least_48`. Use320/360/412 widths and1.0/1.3/2.0 scales, long borrower names, two loans, `'123456789.01'`, and a220 keyboard inset. Keep same one-tap/combined callback counts and payload identity.
- [ ] Run `flutter test test/android_readability_test.dart`. Separate reproduced exceptions/clipping from layouts that already pass; do not rewrite a passing approved layout merely for symmetry.
- [ ] Replace fixed maximum heights with minimum/natural heights, allow fewer overview columns and stacked full monetary values when needed, and give status/action text adequate space. Keep default-width restored Management grouping, Collector primary row/actions and full authorized details. Do not clamp scaling, shrink font, ellipsize amounts or change payment confirmation semantics.
- [ ] Run new tests plus `collector_client_ledger_test.dart`, `collection_entry_page_test.dart`, `management_review_test.dart`, `client_dashboard_test.dart`. Inspect actual Flutter captures for changed states; a passing exception check alone is insufficient.
- [ ] Commit `fix(android): adapt role screens to narrow and large-text layouts`.

## Task 4 — Shared secondary labels and deliberate permission presentation (A4)

**Files:** Edit `daily_workspace_widgets.dart`, four home/menu files and read-only routing tests. Add `test/android_secondary_navigation_test.dart`; preserve enhanced routing/mirror tests identified Task0.

**Interfaces:** Colocate constant labels in existing shared widgets; reuse current AccountSettingsPage, NotificationCenterPage and MobileOfflinePolicyPage. Keep original navigation functions and session. No new route registry or role switch.

- [ ] Write `secondary_labels_match_across_roles`, `management_restore_and_single_workspace_survive`, `collector_primary_flow_remains_route_first`, `optional_unauthorized_tool_is_hidden`, `fixed_unavailable_destination_explains_disabled_state`, and `navigation_preserves_pending_work_and_private_boundaries`. Test single roles, Management+other roles and Employee+Collector; verify an unauthorized entry cannot dispatch a network call.
- [ ] Run `flutter test test/android_secondary_navigation_test.dart`; record only specified label/access-presentation failures. Do not treat intentionally different home layouts as a failed test.
- [ ] Use Profile & security / Notifications / Offline & sync / Sign out consistently. Keep Management top-bar Sign out and restored grouping; keep Employee/Client menu and Client bell; keep Collector More and primary destination order. Hide optional inaccessible business tools; fixed navigation has disabled semantics with a visible explanation rather than an enabled false workflow. Revalidate current permission on navigation and retain privacy hooks.
- [ ] Run new tests plus `daily_workspace_widgets_test.dart`, `employee_dashboard_test.dart`, `client_dashboard_test.dart`, root routing and mirror tests. Back returns to the prior safe context without recreating financial attempts.
- [ ] Commit `refactor(android): align secondary navigation without replacing role homes`.

## Task 5 — Exact display contracts and visible SPINA wording (A5)

**Files:** Create `src/core/formatting/spina_display.dart`; preserve `formatClientLoanMoney` compatibility in core/loans; update reviewed role display call sites and explicit visible branding. Add `test/spina_display_test.dart` and `test/android_display_consistency_test.dart`.

**Interfaces:** `String formatSpinaMoney(String? value, {bool compact = false})`; `String formatSpinaCalendarDate(String? value)` for validated date-only text; `String formatSpinaInstant(DateTime? value)` delegates existing business-time conversion. Existing model/input/time request APIs remain unchanged. No double input in the exact-text formatter; numeric legacy call sites use an explicit existing validated conversion at the boundary and record limitations.

- [ ] Write exact assertions for money `'12345.60'`, `'-50.00'`, `'0'`, `'1.2345'`, null and malformed text; compact `'1200.00'`/`'1200.50'`; adjacent large values `'90071992547409.91'`/`'90071992547409.92'` remain different strings. Calendar `2026-10-02` stays that date; instant `2026-10-01T16:30:00Z` displays `2026-10-02 00:30` in Manila, regardless of test device zone. Test missing date as Not recorded and malformed as Unavailable.

```dart
expect(formatSpinaMoney('12345.60'), '₱12,345.60');
expect(formatSpinaMoney('1200.00', compact: true), '₱1,200');
expect(formatSpinaMoney('1200.50', compact: true), '₱1,200.50');
expect(formatSpinaMoney(null), 'Unavailable');
expect(formatSpinaCalendarDate('2026-10-02'), '2026-10-02');
```

- [ ] Run `flutter test test/spina_display_test.dart test/android_display_consistency_test.dart`; confirm current incompatible display, not an unrelated arithmetic failure.
- [ ] Extract/reuse the existing exact Client grouping/precision behavior. Keep its old formatter callable; migrate only display sites. Do not round extra precision or use formatted output in payloads. Use date-only and instant helpers separately. Replace app-authored visible Gilbic copy; leave package/API/store/user text untouched. Inventory directly reachable remaining divergences and explain any scoped follow-up.
- [ ] Run new tests, existing exact money/time tests found Task0, Collector ledger/Client/Employee presentation tests and guarded request regression. Compare representative before/after financial payloads for byte-identical amount/identity fields. No new double-based parser or backend change.
- [ ] Commit `refactor(android): standardize exact money dates and visible branding`.

## Task 6 — Curated shared Employee record hierarchy (A6)

**Files:** Create `src/features/employee/employee_record_presentation.dart`; edit EmployeeOperationsPage only for read presentation. Add `test/employee_record_presentation_test.dart`; preserve `employee_operations_widget_test.dart` and command/service suites.

**Interfaces:** `EmployeeRecordPresentation presentEmployeeRecord(String collection, Map<String,dynamic> record, String employeeName)` produces display `title`, `summaryFields`, and ordered `detailKeys`. It accepts already-authorized records, never calculates money or chooses allowed actions. Existing safe recursive detail renderer/history and command callbacks remain reusable; unknown collections fall back safely.

- [ ] Write `payroll_approved_is_not_paid`, `summary_uses_supplied_values_only`, `details_preserve_all_authorized_fields`, `excluded_metadata_stays_hidden`, `unknown_record_retains_safe_details`, `command_receives_original_id_and_version`, and `shared_roles_keep_distinct_authority`. Cover attendance/request/task/advance/payroll/shortage/accounting, missing setup, unknown fields, histories and long content.
- [ ] Run `flutter test test/employee_record_presentation_test.dart`; confirm generic hierarchy/missing distinction failures without altering backend state.
- [ ] Show status/date/period/relevant supplied money/action first. Keep record/version/references under Details and all authorized history under Record history in server order. Do not newly expose suppressed fields or derive net/deductions/paid balance. Keep raw source data intact, owner-only and independent-approval filters unchanged; protect draft/evidence state when details expand/collapse.
- [ ] Run new and existing Operations/command tests; inspect shared Employee page as Employee, Collector and Management. Assert every original permitted action still calls the original command and no new action/grant/print system exists.
- [ ] Commit `refactor(android): clarify employee record summaries and history`.

## Task 7 — Offline and in-progress consistency without changing storage (A7)

**Files:** Bounded copy/status edits in EmployeeOperationsPage, offline policy page and Collector guidance; shared notices as needed. Add `test/android_offline_state_consistency_test.dart`; existing attendance/outbox/payment/session/mirror suites are read/reused, not rewritten for convenience.

**Interfaces:** Consume actual AttendanceEntry.state/binding and existing financial pending/guard state. Presentation maps states to the spec's distinct explanations; no new queue, persistence adapter or retry dispatcher.

- [ ] Write `device_saved_attendance_is_not_server_accepted`, `attendance_pending_survives_reopen_same_scope`, `other_account_never_sees_old_attendance`, `financial_offline_stays_blocked`, `read_retry_does_not_unlock_uncertain_payment`, `navigation_does_not_replace_pending_identity`, and `denied_scope_clears_private_view`. Include network loss during submit, current token rotation, device/grant change, restart via existing fake protected stores and already-accepted attendance.
- [ ] Run `flutter test test/android_offline_state_consistency_test.dart`; pin misleading presentation if present and retain already-correct guards. Do not manufacture a failing financial rule to justify edits.
- [ ] Align device-saved/server-received/review/readonly/online-required wording while retaining actual service behavior. Generic read recovery cannot call a financial POST or reset its identity. Keep safe approved attendance sync, account binding, pending file retention and denied-data cleanup intact. Report any deeper persistence defect separately instead of broad refactoring.
- [ ] Run the new suite plus current outbox/service/payment/session/private-surface regressions from Task0; verify zero financial writes while offline and no cross-actor read/write leakage. Mock screen-sharing tracks; do not start actual sharing.
- [ ] Commit `fix(android): distinguish offline attendance from financial recovery` only for implemented changes; keep passing tests/evidence when no product change is necessary.

## Task 8 — Production-theme native consistency and accessibility evidence (A8)

**Files:** Add `test/android_role_consistency_matrix_test.dart`, `test/android_accessibility_consistency_test.dart`; use Task0 harness/fakes. Update existing Client dashboard tests to exercise production theme and assert the intended scale actually reaches descendants. No production demo route or dependency upgrade.

**Interfaces:** Matrix dimensions/fixture identities are centralized in test support. Named evidence entries include role, logical size, TextScaler, actual observed scale, state, source SHA, Flutter revision, screenshot path and outcome. Golden/reference updates require visual review; no auto-accepting failing baselines.

- [ ] Write the matrix over Management/Employee/Collector/Client x320x640,360x640,412x915 x1.0,1.3,2.0. Assert production theme and descendant scaler, no swallowed exceptions, readable exact money/status, reachable required actions and no unexpected network/mutation. Render and inspect all scrollable sections, not only the initial viewport.
- [ ] Run `flutter test test/android_role_consistency_matrix_test.dart test/android_accessibility_consistency_test.dart`. Fix only scoped regressions with focused tests; track each failing/blocked combination. Do not claim36 passes from36 generated filenames.
- [ ] Add native semantic checks on representative live widgets after loading, errors, menus and dialogs:

```dart
final handle = tester.ensureSemantics();
addTearDown(handle.dispose);
await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
await expectLater(tester, meetsGuideline(textContrastGuideline));
```

- [ ] Exercise the additional A8 workflow/state matrix from the spec: keyboard220/Back/landscape/tablet/reduced-motion, single/combined financial forms and uncertainty, Client schedule recovery, Employee work/pay/history and Management confirmation/limited access. Failures cannot be waived solely because default home passed.
- [ ] Use actual Flutter widget captures and an isolated Android emulator fixture host with no live server. Check maximum OS font setting/nonlinear scaling, TalkBack labels/order/actions and Android Accessibility Scanner; record device/emulator/API/density/font settings and synthetic evidence. Unavailable emulator/TalkBack remains blocked separately from widget/CI success. Do not install over the owner's production app or initiate signed delivery.
- [ ] Commit reviewed fixture/test improvements and evidence index as `test(android): verify cross-role native consistency and accessibility`. Keep screenshots secret-free and out of shipping assets. Do not change financial assertions, production theme, viewport or test font scale to hide failures.

## Task 9 — Exact-head integration, CI and owner handoff (A8)

**Files:** This checklist/evidence index; read/reuse `.github/workflows/spina-ci.yml`, `tools/prepare_android_host.py`, `tools/verify_android_artifact.py`. No new CI/build system.

- [ ] Reconcile A1–A8 against code/tests/native evidence and Task0 inventory. Document confirmed fixes versus layout risks tested, unsupported channel/precision contracts, legitimate navigation exceptions and missing device evidence. Preserve #464 and one-tap behavior with direct regression references.
- [ ] With the repository's current pinned toolchain, run focused suites during iteration and final full native checks once on the actual integration head:

```sh
cd gilbic_mobile
flutter pub get --enforce-lockfile
flutter analyze --fatal-infos
flutter test
cd ..
git diff --check
```

Format only touched Dart files with the existing tooling, then verify them. If baseline formatter/scanner issues exist, report them rather than broadly reformatting or weakening CI. Do not run a second identical full suite on an unchanged head merely for receipts.

- [ ] Let existing PR CI run its normal three jobs: **Backend, quality, and security**; **Portal, Flutter, and Android**; **Financial and disposable PostgreSQL**. Inspect exact-head job/run results and the existing generated-host internal Android verification. Do not assume a plain `flutter build apk` in this source directory replaces that host workflow. No manual duplicate delivery run or production endpoint probe.
- [ ] Record APK/source hash and verification metadata if the existing CI artifact is available. An internal debug build verifies packaging only, not phone installation, release signer compatibility, TalkBack or usability. Do not bump app version, use private keys, uninstall an app or claim an in-place upgrade. Those remain owner-controlled release evidence.
- [ ] Review final diff and other-platform compilation/theme behavior; coordinate shared backend contract observations with Web485–488 without editing their scope or importing their JS controllers. Keep any non-Android feature request as an explicit disposition, not an undocumented stub.
- [ ] Update PR from planning-only only when actual product commits exist. Keep Draft/open/unmerged and automatic merge off. Synchronize GitHub/Notion/Create State with exact SHA, completed/pending tasks, CI, native matrix, actual/blocked TalkBack/emulator evidence, limitations and next owner action. Disclose failed sync; no Master CA checkboxes, merge/deploy/delivery or signed install.

## Completion ledger

Every row below is pending at planning handoff. Replace with commit/test/evidence references only after execution.

| Task | Review coverage | State |
| --- | --- | --- |
| 0 | Baseline, restore/ownership, production-theme fixture | Pending Codex |
| 1 | A1 channel truth, status meaning and semantic style | Not implemented |
| 2 | A2 correct actions and visible same-loan recovery | Not implemented |
| 3 | A3 adaptive readability/touch targets without redesign | Not implemented |
| 4 | A4 secondary labels, role routing and permission presentation | Not implemented |
| 5 | A5 exact display/copy/calendar-versus-instant contract | Not implemented |
| 6 | A6 shared Employee summaries with retained details/history | Not implemented |
| 7 | A7 offline/uncertainty/privacy distinctions and regression | Not implemented |
| 8 | A8 36 native widget configurations plus actual device/accessibility evidence | Not run |
| 9 | A8 integrated checks, exact-head CI/artifact and synchronized handoff | Not run |

A docs-only Green does not complete this ledger. Owner Red/Green feedback must be resolved to the exact current commit/jobs; partial native evidence stays partial. No new UI screenshot, widget result, TalkBack pass or installed build is claimed by these Markdown files.

## Copyable Codex task

Implement this Android cross-role consistency plan on this Draft PR's existing branch `plan/android-cross-role-ui-consistency-20261002`. Read this plan/spec, live main/open PRs, frozen296 with later scope, approved369, Management restoration464, Android review448/comment5944212677, latest Notion and Create State. Follow Tasks0–9 with failing behavioral evidence before fixes and small reviewed passing commits. Preserve the restored Management layout and single workspace, Collector route-first/one-tap/atomic behavior, exact server money, permissions, independent confirmations, online-only financial safeguards, protected offline attendance, pending identities and private-screen boundaries. Reuse the theme and shared pages; no new framework/backend grant/endpoint/persistence/version/signing change. Complete truthful statuses/recovery, adaptive text/touch layout, secondary wording, exact display and Employee detail hierarchy. Prove36 production-theme native configurations plus the specified workflow/semantic checks; report actual versus blocked emulator/TalkBack evidence honestly. Do not treat Web screenshots, old CI or a debug APK as native usability acceptance. Keep Web485–488 separate, update task evidence and GitHub/Notion/Create State, and use this same PR rather than a duplicate. Leave Draft/open/unmerged; no mark-ready/merge/deploy/delivery/migrations/production credentials or transactions/real sharing/owner-device installation/Master acceptance changes. Finish with exact head, results, native evidence, remaining gaps and next owner action.
