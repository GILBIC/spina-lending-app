# CA2 Management Review Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every current state-changing Management workflow one server-grounded review and confirmation pattern that identifies the record, current status, warnings, next action, and exact consequence.

**Architecture:** Add a presentation-only review module under the Management feature boundary. Each existing page maps its typed FastAPI response into immutable display data while retaining permission checks, forms, repository calls, payloads, idempotency, reloads, and error recovery. A source inventory test guards all 13 known mutation surfaces against drift.

**Tech Stack:** Flutter/Dart, Material 3 widgets, `flutter_test`, existing typed Management repositories and FastAPI contracts.

**Spec:** `docs/superpowers/specs/2026-08-29-ca2-management-review-consistency-design.md`

## Global Constraints

- Start at commit `cc27f844` on `codex/ca2-management-review-consistency`, stacked on Draft PR #377.
- FastAPI and PostgreSQL remain authoritative; Flutter does not infer permissions, eligibility, balances, readiness, warnings, accounting outcomes, or official mutation results.
- Do not change API routes, payloads, repository signatures, roles, permissions, device rules, idempotency, audit events, or financial rules.
- Primary copy is plain operational/accounting language. Raw statuses and audit references are secondary detail only.
- Missing or unknown facts remain neutral and never become `No`, `Zero`, `Clear`, `Eligible`, `Ready`, or `Approved`.
- The shared module has no repository or HTTP dependency and returns only widgets or confirm/cancel.
- Existing pages retain mutation ownership, progress locking, denial handling, stale-conflict handling, uncertain-result recovery, and authoritative refresh.
- Protected financial mutations remain online-only.
- Modified pages scroll at 360x640 logical pixels with 1.3x text scaling.
- Do not merge, deploy, restart protected services, mutate protected/live data, or mark Management/Android/iOS acceptance complete.
- Work test-first and stage only files named in the current task.

## File Structure

- Create `gilbic_mobile/lib/src/features/management/review/management_review.dart` for immutable display types, the 13-surface catalog, panel, and confirmation helper.
- Create `gilbic_mobile/test/management_review_test.dart` for the shared contract, widgets, semantics, and responsive layout.
- Create `gilbic_mobile/test/management_review_surface_inventory_test.dart` for exact catalog behavior and read-only-page classification; owning page tests provide the reachable-widget proof.
- Modify the 13 owning Management pages listed in the approved spec.
- Extend each existing focused page test. Create `client_registration_approvals_page_test.dart` and `management_no_collection_page_test.dart`, which do not exist at the starting commit.

---

### Task 1: Shared review contract and widgets

**Files:**
- Create: `gilbic_mobile/lib/src/features/management/review/management_review.dart`
- Create: `gilbic_mobile/test/management_review_test.dart`

**Interfaces:**
- Consumes: Flutter `material.dart` only.
- Produces: `ManagementMutationSurface`, `ManagementReviewRisk`, `ManagementReviewWarningSeverity`, `ManagementReviewWarning`, `ManagementReviewFact`, `ManagementReviewPresentation`, `ManagementReviewPanel`, `plainManagementStatus`, and `showManagementReviewConfirmation`.

- [ ] **Step 1: Write the failing shared tests**

Use this exact public construction in the test:

```dart
final review = ManagementReviewPresentation.validated(
  surface: ManagementMutationSurface.collectionVoid,
  recordLabel: 'Official receipt',
  recordValue: 'OR-2026-0042 • Maria Santos',
  statusLabel: 'Eligible for protected correction',
  statusDetail: 'Server status: unlocked_unremitted',
  facts: const <ManagementReviewFact>[
    ManagementReviewFact(label: 'Amount', value: '₱500.00'),
  ],
  warnings: const <ManagementReviewWarning>[
    ManagementReviewWarning(
      severity: ManagementReviewWarningSeverity.caution,
      message: 'The client balance will be restored.',
    ),
  ],
  nextActionLabel: 'Void this collection',
  consequence:
      'The receipt will be voided, the client balance will be restored, and permanent audit evidence will remain.',
  risk: ManagementReviewRisk.protectedFinancial,
  secondaryReferences: const <ManagementReviewFact>[
    ManagementReviewFact(label: 'Transaction reference', value: 'txn-42'),
  ],
);
```

Assert the stable key, all five headings in order, warning icon plus semantics, secondary reference, cancel/confirm return values, 360x640 at 1.3x text scale, blank-value rejection, blocker/action-enabled rejection, known status translation, neutral missing status, and neutral unknown status.

- [ ] **Step 2: Run the test to prove red**

```powershell
flutter test test/management_review_test.dart
```

Expected: compile failure because the shared module does not exist.

- [ ] **Step 3: Implement the immutable API**

Use these exact enums and status helper:

```dart
enum ManagementReviewRisk { routine, privileged, protectedFinancial }
enum ManagementReviewWarningSeverity { information, caution, blocker }

enum ManagementMutationSurface {
  clientRegistration('client-registration'),
  renewalWorkflow('renewal-workflow'),
  staffInvitation('staff-invitation'),
  staffAccess('staff-access'),
  collectionVoid('collection-void'),
  contractCollection('contract-collection'),
  noCollection('no-collection'),
  clientSupport('client-support'),
  eclOutcomeReview('ecl-outcome-review'),
  fiscalPeriod('fiscal-period'),
  generalJournal('general-journal'),
  openingWorkbook('opening-workbook'),
  openingJournal('opening-journal');

  const ManagementMutationSurface(this.id);
  final String id;
}

String plainManagementStatus(
  String? raw,
  Map<String, String> known, {
  String missing = 'Not provided by the server',
}) {
  final normalized = raw?.trim().toLowerCase() ?? '';
  if (normalized.isEmpty) return missing;
  return known[normalized] ?? 'Status needs review';
}
```

`ManagementReviewPresentation.validated` requires nonblank record label/value, status, next action, and consequence. It rejects enabled actions with a blocker. Its `key` is `Key('management-review-${surface.id}')`.

- [ ] **Step 4: Implement panel and confirmation widgets**

`ManagementReviewPanel` renders `Reviewing`, `Current status`, `Check before continuing`, `Next action`, and `If confirmed` in that order. Use icons and semantic labels as well as color, wrapping columns, selectable secondary references, and no fixed height.

The helper has this signature and behavior:

```dart
Future<bool> showManagementReviewConfirmation(
  BuildContext context,
  ManagementReviewPresentation review,
) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(review.nextActionLabel),
      content: SingleChildScrollView(
        child: ManagementReviewPanel(review: review, compact: true),
      ),
      actions: <Widget>[
        TextButton(
          key: Key('cancel-${review.surface.id}'),
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: Key('confirm-${review.surface.id}'),
          onPressed: review.actionEnabled
              ? () => Navigator.of(context).pop(true)
              : null,
          child: Text(review.nextActionLabel),
        ),
      ],
    ),
  );
  return result == true;
}
```

- [ ] **Step 5: Verify and commit Task 1**

```powershell
flutter test test/management_review_test.dart
flutter analyze --fatal-infos lib/src/features/management/review/management_review.dart test/management_review_test.dart
git add -- gilbic_mobile/lib/src/features/management/review/management_review.dart gilbic_mobile/test/management_review_test.dart
git commit -m "feat: add Management review presentation contract"
```

Expected: tests and analyzer pass before commit.

### Task 2: Mutation-surface inventory guard

**Files:**
- Modify: `gilbic_mobile/lib/src/features/management/review/management_review.dart`
- Create: `gilbic_mobile/test/management_review_surface_inventory_test.dart`

**Interfaces:**
- Consumes: Task 1 surface/risk enums.
- Produces: `ManagementMutationSurfaceEntry` and `managementMutationSurfaceCatalog` for presentation/testing only.

- [ ] **Step 1: Write the failing exact-catalog test**

```dart
const expected = <String>{
  'client-registration', 'renewal-workflow', 'staff-invitation',
  'staff-access', 'collection-void', 'contract-collection',
  'no-collection', 'client-support', 'ecl-outcome-review',
  'fiscal-period', 'general-journal', 'opening-workbook', 'opening-journal',
};
expect(managementMutationSurfaceCatalog, hasLength(13));
expect(
  managementMutationSurfaceCatalog.map((entry) => entry.surface.id).toSet(),
  expected,
);
```

Each entry includes `surface`, `owner`, `actions`, and `defaultRisk`. Assert every enum value appears once, IDs are unique, owners/actions are nonblank, actions are nonempty, and every default risk is rendered by the real shared panel with accessible severity/action semantics. Explicitly classify dashboard, portfolio, loan operations, accounting measurement, financial statements, General Journal launcher, and staff/device directory as read-only containers. Do not read or grep Dart source files; Tasks 3-7 prove actual page behavior.

Populate the catalog with these exact mappings:

| Surface | Owning page | Actions | Default risk |
| --- | --- | --- | --- |
| `clientRegistration` | `lib/src/features/management/client_registration_approvals_page.dart` | approve/link; reject | privileged |
| `renewalWorkflow` | `lib/src/features/management/management_renewal_requests_page.dart` | record terms; reject; release; review proof; activate | privileged |
| `staffInvitation` | `lib/src/features/management/management_staff_invite_page.dart` | invite; reconcile uncertain result | privileged |
| `staffAccess` | `lib/src/features/management/management_staff_detail_page.dart` | change role; change account status; approve/revoke device | privileged |
| `collectionVoid` | `lib/src/features/management/management_collection_void_page.dart` | void eligible collection | protected financial |
| `contractCollection` | `lib/src/features/management/management_contract_collection_activation_page.dart` | activate; deactivate | privileged |
| `noCollection` | `lib/src/features/management/management_no_collection_page.dart` | declare; reverse | protected financial |
| `clientSupport` | `lib/src/features/management/management_support_requests_page.dart` | answer; resolve; cancel | routine |
| `eclOutcomeReview` | `lib/src/features/management/management_ecl_outcome_review_page.dart` | save historical outcome review | privileged |
| `fiscalPeriod` | `lib/src/features/management/management_financial_accounting_page.dart` | create period; change status | protected financial |
| `generalJournal` | `lib/src/features/management/management_general_journal_page.dart` | create/edit draft; post; cancel; create reversal draft | protected financial |
| `openingWorkbook` | `lib/src/features/management/management_opening_balance_workbook_page.dart` | initialize; edit line/policy; change status | protected financial |
| `openingJournal` | `lib/src/features/management/management_opening_balance_journal_page.dart` | prepare; post | protected financial |

- [ ] **Step 2: Run red, implement the catalog, and turn the guard green**

```powershell
flutter test test/management_review_surface_inventory_test.dart
```

First expected failure: catalog missing. After adding the exact 13 spec rows, rerun and expect PASS for exact IDs, unique ownership, actions, risk presentation, and read-only classification. Actual owning-page review behavior remains red/green work in Tasks 3-7.

- [ ] **Step 3: Commit the green catalog guard**

```powershell
git add -- gilbic_mobile/lib/src/features/management/review/management_review.dart gilbic_mobile/test/management_review_surface_inventory_test.dart
git commit -m "test: inventory Management mutation reviews"
```

### Task 3: Client registration and staff administration

**Files:**
- Modify: `gilbic_mobile/lib/src/features/management/client_registration_approvals_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_staff_invite_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_staff_detail_page.dart`
- Create: `gilbic_mobile/test/client_registration_approvals_page_test.dart`
- Modify: `gilbic_mobile/test/management_staff_invite_page_test.dart`
- Modify: `gilbic_mobile/test/management_staff_detail_page_test.dart`

**Interfaces:**
- Consumes: Task 1 review API.
- Produces: `client-registration`, `staff-invitation`, and `staff-access` usage without changing any repository call.

- [ ] **Step 1: Add failing key/cancel/payload tests**

Assert `management-review-client-registration`, `management-review-staff-invitation`, and `management-review-staff-access`. Cancellation performs zero writes; confirmation passes the existing user/candidate, invitation, role/status, and device arguments unchanged. Preserve uncertain invitation recheck and self-action blockers.

```dart
expect(find.byKey(const Key('management-review-staff-access')), findsOneWidget);
await tester.tap(find.byKey(const Key('cancel-staff-access')));
expect(repository.mutationCalls, isEmpty);
```

- [ ] **Step 2: Run the three files to prove red**

```powershell
flutter test test/client_registration_approvals_page_test.dart test/management_staff_invite_page_test.dart test/management_staff_detail_page_test.dart
```

- [ ] **Step 3: Integrate registration review**

Use `registration.fullName`, `claimedClientCode`, `username`, and `registrationStatus`. Map `pending` to `Waiting for Management review`. Approval consequence: `This login will be linked to the selected existing client record; official financial records will not be edited.` Rejection consequence: `This registration request will be rejected; official client and financial records will not be edited.` Keep candidate search and repository payloads unchanged.

- [ ] **Step 4: Integrate staff invitation/access**

Invitation consequence: `A pending staff account will be created with the selected canonical role; access still depends on server status and device approval.` Uncertain outcome next action is `Check the server result`, never a repost.

Map account statuses `pending`, `active`, `inactive`, `revoked` and device statuses `pending`, `active`, `revoked` to plain labels. Use account full name/username and platform/app version. Never render auth IDs, device hashes, or secrets. Keep destructive styling and permission/self guards.

- [ ] **Step 5: Verify and commit Task 3**

```powershell
flutter test test/client_registration_approvals_page_test.dart test/management_staff_invite_page_test.dart test/management_staff_detail_page_test.dart
flutter analyze --fatal-infos lib/src/features/management/client_registration_approvals_page.dart lib/src/features/management/management_staff_invite_page.dart lib/src/features/management/management_staff_detail_page.dart
git add -- gilbic_mobile/lib/src/features/management/client_registration_approvals_page.dart gilbic_mobile/lib/src/features/management/management_staff_invite_page.dart gilbic_mobile/lib/src/features/management/management_staff_detail_page.dart gilbic_mobile/test/client_registration_approvals_page_test.dart gilbic_mobile/test/management_staff_invite_page_test.dart gilbic_mobile/test/management_staff_detail_page_test.dart
git commit -m "feat: standardize Management access reviews"
```

### Task 4: Renewals, collection void, contract collection, and No Collection

**Files:**
- Modify: `gilbic_mobile/lib/src/features/management/management_renewal_requests_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_collection_void_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_contract_collection_activation_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_no_collection_page.dart`
- Modify: `gilbic_mobile/test/management_renewal_requests_page_test.dart`
- Modify: `gilbic_mobile/test/management_collection_void_page_test.dart`
- Modify: `gilbic_mobile/test/management_contract_collection_activation_page_test.dart`
- Create: `gilbic_mobile/test/management_no_collection_page_test.dart`

**Interfaces:**
- Consumes: shared review API and existing typed server records/previews.
- Produces: `renewal-workflow`, `collection-void`, `contract-collection`, and `no-collection` usage with unchanged IDs, versions, reasons, dates, notes, proofs, and idempotency.

- [ ] **Step 1: Write failing review/cancel/payload/responsive tests**

```dart
const keys = <String>{
  'management-review-renewal-workflow',
  'management-review-collection-void',
  'management-review-contract-collection',
  'management-review-no-collection',
};
```

Cancel performs zero writes. Accepted paths preserve all existing payload fields. Test No Collection and renewal dialogs at 360x640/1.3x.

- [ ] **Step 2: Run four files to prove red**

```powershell
flutter test test/management_renewal_requests_page_test.dart test/management_collection_void_page_test.dart test/management_contract_collection_activation_page_test.dart test/management_no_collection_page_test.dart
```

- [ ] **Step 3: Integrate renewal and contract collection**

Renewal consequences are exact: terms save does not release/activate; reject retains current loan authority; Collector release is field coordination, not activation; proof review records acceptance/rejection only; activation is shown only after authoritative refresh.

Contract source is loan number/client name. Warnings come only from `loan.blockers`. Activation enables mobile collection only for the verified current schedule; deactivation blocks it until later Management reactivation. Preserve permission, can-activate/deactivate, schedule version, and calls.

- [ ] **Step 4: Integrate collection void and No Collection**

Collection source is receipt/client, with amount, collector, date, and official balance from the candidate. Consequence states receipt void, restored balance, and permanent audit evidence.

No Collection uses loaded loan state plus server preview. Show schedule/operational versions, selected date, affected installment count, and returned blockers/shifts. Consequences are:

```dart
const declarationConsequence =
    'The server will record the No Collection date and shift the reviewed unpaid installments while preserving the contractual schedule and audit evidence.';
const reversalConsequence =
    'The server will reverse this No Collection adjustment against the current operational version and preserve both actions in audit history.';
```

Never calculate shifts or reuse a preview after the operational version changes.

- [ ] **Step 5: Verify and commit Task 4**

```powershell
flutter test test/management_renewal_requests_page_test.dart test/management_collection_void_page_test.dart test/management_contract_collection_activation_page_test.dart test/management_no_collection_page_test.dart
flutter analyze --fatal-infos lib/src/features/management/management_renewal_requests_page.dart lib/src/features/management/management_collection_void_page.dart lib/src/features/management/management_contract_collection_activation_page.dart lib/src/features/management/management_no_collection_page.dart
git add -- gilbic_mobile/lib/src/features/management/management_renewal_requests_page.dart gilbic_mobile/lib/src/features/management/management_collection_void_page.dart gilbic_mobile/lib/src/features/management/management_contract_collection_activation_page.dart gilbic_mobile/lib/src/features/management/management_no_collection_page.dart gilbic_mobile/test/management_renewal_requests_page_test.dart gilbic_mobile/test/management_collection_void_page_test.dart gilbic_mobile/test/management_contract_collection_activation_page_test.dart gilbic_mobile/test/management_no_collection_page_test.dart
git commit -m "feat: standardize Management lending reviews"
```

### Task 5: Client support and historical ECL outcome

**Files:**
- Modify: `gilbic_mobile/lib/src/features/management/management_support_requests_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_ecl_outcome_review_page.dart`
- Modify: `gilbic_mobile/test/management_support_requests_page_test.dart`
- Modify: `gilbic_mobile/test/management_ecl_outcome_review_page_test.dart`

**Interfaces:**
- Consumes: shared review API and existing support/ECL typed records.
- Produces: `client-support` and `ecl-outcome-review` usage with unchanged review payloads.

- [ ] **Step 1: Add failing key/cancel/outcome tests**

Assert both stable keys. Cover support answer/resolve/cancel; ECL source-review blocker, default/non-default choice, immutable history, and no PD/LGD/ECL/GL claim.

- [ ] **Step 2: Run focused tests to prove red**

```powershell
flutter test test/management_support_requests_page_test.dart test/management_ecl_outcome_review_page_test.dart
```

- [ ] **Step 3: Integrate support and ECL review**

Support consequences: an answer becomes communication history; resolved closes with response; cancelled closes without changing financial records.

ECL source is privacy-safe episode/borrower information already shown. Map source-quality and review statuses separately. Source-review-required is a blocker. Use this consequence:

```dart
const eclConsequence =
    'A new immutable historical outcome-review version will be saved. This does not calculate loss, recovery, PD, LGD or ECL and does not post to the General Ledger.';
```

Preserve evidence, label, version, permission, and repository arguments.

- [ ] **Step 4: Verify and commit Task 5**

```powershell
flutter test test/management_support_requests_page_test.dart test/management_ecl_outcome_review_page_test.dart
flutter analyze --fatal-infos lib/src/features/management/management_support_requests_page.dart lib/src/features/management/management_ecl_outcome_review_page.dart
git add -- gilbic_mobile/lib/src/features/management/management_support_requests_page.dart gilbic_mobile/lib/src/features/management/management_ecl_outcome_review_page.dart gilbic_mobile/test/management_support_requests_page_test.dart gilbic_mobile/test/management_ecl_outcome_review_page_test.dart
git commit -m "feat: standardize Management service reviews"
```

### Task 6: Fiscal periods

**Files:**
- Modify: `gilbic_mobile/lib/src/features/management/management_financial_accounting_page.dart`
- Modify: `gilbic_mobile/test/management_financial_accounting_page_test.dart`

**Interfaces:**
- Consumes: shared review API and `AccountingFiscalPeriod`.
- Produces: `fiscal-period` usage for creation/status changes with unchanged repository calls.

- [ ] **Step 1: Add failing creation/status tests**

Require period label/date range, current plain status, journal counts, next state, consequence, stable key, cancel-no-call, and unchanged accepted payload.

```dart
expect(find.byKey(const Key('management-review-fiscal-period')), findsOneWidget);
expect(find.text('Change period to Closed'), findsOneWidget);
```

- [ ] **Step 2: Run focused test to prove red**

```powershell
flutter test test/management_financial_accounting_page_test.dart
```

- [ ] **Step 3: Integrate fiscal-period review**

Map `open` to `Open for permitted journal work`, `review` to `Waiting for Management review`, and `closed` to `Closed to new journal work`. Creation does not post a journal/balance. Review transition describes server restrictions. Close preserves posted journals. Reopen promises only the target state, not new posting authority. Preserve allowed transitions and `periodManagementEnabled`.

- [ ] **Step 4: Verify and commit Task 6**

```powershell
flutter test test/management_financial_accounting_page_test.dart
flutter analyze --fatal-infos lib/src/features/management/management_financial_accounting_page.dart
git add -- gilbic_mobile/lib/src/features/management/management_financial_accounting_page.dart gilbic_mobile/test/management_financial_accounting_page_test.dart
git commit -m "feat: clarify fiscal period reviews"
```

### Task 7: General Journal and opening balances

**Files:**
- Modify: `gilbic_mobile/lib/src/features/management/management_general_journal_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_opening_balance_workbook_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_opening_balance_journal_page.dart`
- Modify: `gilbic_mobile/test/management_general_journal_page_test.dart`
- Modify: `gilbic_mobile/test/management_opening_balance_workbook_page_test.dart`
- Modify: `gilbic_mobile/test/management_opening_balance_journal_page_test.dart`

**Interfaces:**
- Consumes: shared review API and typed journal/workbook/status data.
- Produces: `general-journal`, `opening-workbook`, and `opening-journal` usage without changing posting, reversal, cutover, or readiness rules.

- [ ] **Step 1: Add failing journal/workbook/opening-journal tests**

Require stable keys for create/edit/post/cancel/reversal, initialize/edit/status, prepare, and post. Verify cancel-no-call, unchanged payloads, exact debit/credit strings, separate prepare/post confirmations, blockers, and 360x640/1.3x layout.

- [ ] **Step 2: Run three test files to prove red**

```powershell
flutter test test/management_general_journal_page_test.dart test/management_opening_balance_workbook_page_test.dart test/management_opening_balance_journal_page_test.dart
```

- [ ] **Step 3: Integrate General Journal**

Show period/date/debit/credit and plain draft/posted state. New/edit save is an unposted draft and does not affect the GL. Posting becomes immutable and corrections require reversal. Cancellation retains audit. Reversal creates a separate swapped-lines draft that must be reviewed/posted. Keep balance/account/date validation and repository methods.

- [ ] **Step 4: Integrate opening workbook**

Initialization snapshots approved references but creates/posts no journal. Line/policy save posts no balance. Status change only changes workflow state; journal preparation/posting remain separate. Use cutover date/status, source references, policy/measurement evidence, and returned readiness without inference.

- [ ] **Step 5: Integrate opening journal**

Use `totalDebitExact`/`totalCreditExact` without double conversion. Warnings come from server blockers and enablement booleans. Preparation creates a separate draft and posts nothing. Posting acts only when `postingReady` and makes the journal immutable with protected reversal evidence. Never equate workbook `review_ready` with posting readiness.

- [ ] **Step 6: Verify and commit Task 7**

```powershell
flutter test test/management_general_journal_page_test.dart test/management_opening_balance_workbook_page_test.dart test/management_opening_balance_journal_page_test.dart
flutter analyze --fatal-infos lib/src/features/management/management_general_journal_page.dart lib/src/features/management/management_opening_balance_workbook_page.dart lib/src/features/management/management_opening_balance_journal_page.dart
git add -- gilbic_mobile/lib/src/features/management/management_general_journal_page.dart gilbic_mobile/lib/src/features/management/management_opening_balance_workbook_page.dart gilbic_mobile/lib/src/features/management/management_opening_balance_journal_page.dart gilbic_mobile/test/management_general_journal_page_test.dart gilbic_mobile/test/management_opening_balance_workbook_page_test.dart gilbic_mobile/test/management_opening_balance_journal_page_test.dart
git commit -m "feat: standardize Management accounting reviews"
```

### Task 8: Inventory closure and exact-head release evidence

**Files:**
- Modify only Task 1-7 files when a test proves a gap.
- Test: full Flutter suite/analyzer/format.
- Evidence: Draft PR, Master Issue, Notion, and Create State; do not commit generated build/cache files.

**Interfaces:**
- Consumes: all 13 migrated surfaces.
- Produces: exact-head Draft PR evidence, not Management acceptance or deployment approval.

- [ ] **Step 1: Close the inventory guard**

Run the catalog test together with every owning-page behavior test. Each page
test must drive the real page to its decision point and observe exactly one
`management-review-<surface-id>` widget. The combined command is the inventory
gate; do not replace it with source-text assertions.

```powershell
flutter test test/management_review_surface_inventory_test.dart
```

Expected: exactly 13 catalog entries, all owning pages use the shared module, and read-only containers remain excluded.

- [ ] **Step 2: Run all focused Management tests together**

```powershell
flutter test test/management_review_test.dart test/management_review_surface_inventory_test.dart test/client_registration_approvals_page_test.dart test/management_staff_invite_page_test.dart test/management_staff_detail_page_test.dart test/management_renewal_requests_page_test.dart test/management_collection_void_page_test.dart test/management_contract_collection_activation_page_test.dart test/management_no_collection_page_test.dart test/management_support_requests_page_test.dart test/management_ecl_outcome_review_page_test.dart test/management_financial_accounting_page_test.dart test/management_general_journal_page_test.dart test/management_opening_balance_workbook_page_test.dart test/management_opening_balance_journal_page_test.dart
```

- [ ] **Step 3: Run complete verification**

```powershell
flutter test
flutter analyze --fatal-infos
dart format --output=none --set-exit-if-changed lib test
git diff --check origin/codex/ca2-management-live-overview...HEAD
```

Expected: all commands exit 0.

- [ ] **Step 4: Inspect authority/privacy scope**

```powershell
git diff --stat origin/codex/ca2-management-live-overview...HEAD
git diff origin/codex/ca2-management-live-overview...HEAD -- gilbic_mobile/lib gilbic_mobile/test
```

Confirm no new API/repository contract, direct DB/Supabase admin access, client financial decision, secret/PII fixture, automatic mutation retry, payload change, or generated file.

- [ ] **Step 5: Build and smoke-test Android review APK**

```powershell
flutter build apk --debug
Get-FileHash build/app/outputs/flutter-apk/app-debug.apk -Algorithm SHA256
adb install -r build/app/outputs/flutter-apk/app-debug.apk
adb shell am force-stop com.gilbic.gilbic_mobile
adb shell monkey -p com.gilbic.gilbic_mobile -c android.intent.category.LAUNCHER 1
```

Record exact commit, path, bytes, SHA-256, install result, and cold-launch fatal-exception result. This remains an unsigned/debug review artifact.

- [ ] **Step 6: Push stacked Draft PR and synchronize status**

Push `codex/ca2-management-review-consistency`; open a Draft PR targeting `codex/ca2-management-live-overview`; link Master Issue #296, parent PR #377, spec, tests, analyzer, APK evidence, and open authenticated Management acceptance. Wait for all permanent CI lanes on the exact head. Update Master Issue, SPINA Notion project memory, and Create State with implemented-versus-intended wording. Leave CA2, Android approval, iOS, merge, deployment, and later dependency gates open.
