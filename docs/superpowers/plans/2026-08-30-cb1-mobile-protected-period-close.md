# CB1 Mobile Protected Period Close Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Gilbic Mobile's rejected generic fiscal-period close action with the existing protected retained-earnings prepare/post workflow.

**Architecture:** FastAPI adds mobile route aliases to the existing protected handlers; no accounting logic is copied or changed. Flutter adds a typed read/write adapter and a Management review page that submits exact server snapshot values, then the existing Financial Accounting page links to it and stops offering direct close.

**Tech Stack:** Python 3.11+, FastAPI, PostgreSQL protected functions, Flutter 3.44.7/Dart, `http`, Flutter widget tests, pytest.

**Spec:** `docs/superpowers/specs/2026-08-30-cb1-mobile-protected-period-close.md`

## Execution status — 2026-08-30

- Tasks 1–4 are implemented and locally verified on
  `codex/cb1-mobile-period-close`.
- Task 5 local verification is complete: FastAPI contract 6/6, focused Flutter
  20/20, full Flutter 400/400, full backend 1,282 passed with 188 configured
  integration skips, strict Flutter analysis clean, and Dart formatting clean.
- Draft PR publication, exact-head CI, and GitHub/Notion status synchronization
  remain the active checkpoint. Nothing in this plan authorizes merge,
  production migration, signing, deployment, or release.

## Global Constraints

- Reuse the existing `period_close_api.py` handlers and SQL 0091/0092 authority.
- Do not add or change SQL, retained-earnings calculations, tax logic, ECL logic, or automatic posting.
- Require active approved-device authentication and server-derived Management permissions.
- Use exact server values for digest, net income, account `3100`, and period end date.
- Preserve one confirmation token for an uncertain retry of the same prepared digest.
- Keep CA6/CA7, production signing, deployment, and human-review gates separate.

---

### Task 1: Expose the protected period-close handlers to mobile

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/period_close_api.py`
- Modify: `gilbic_backend/tests/test_period_close_api_contract.py`

**Interfaces:**
- Consumes: existing `list_period_close_items`, `prepare_period_close`, and `post_period_close` handlers.
- Produces: `/api/mobile/v1/management/financial-accounting/period-close`, `/{fiscal_period_id}/prepare`, and `/{fiscal_period_id}/post` aliases with identical payloads.

- [ ] **Step 1: Write the failing contract test**

```python
def test_period_close_api_exposes_same_handlers_to_mobile() -> None:
    for route in (
        '"/api/mobile/v1/management/financial-accounting/period-close"',
        '"/api/mobile/v1/management/financial-accounting/period-close/{fiscal_period_id}/prepare"',
        '"/api/mobile/v1/management/financial-accounting/period-close/{fiscal_period_id}/post"',
    ):
        assert route in API
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest -q gilbic_backend/tests/test_period_close_api_contract.py`

Expected: failure because the three mobile strings are absent.

- [ ] **Step 3: Add alias decorators to the existing handlers**

```python
@router.get(
    "/api/mobile/v1/management/financial-accounting/period-close",
    include_in_schema=False,
)
```

Add equivalent `@router.post(..., include_in_schema=False)` decorators for prepare and post. Do not add wrapper functions.

- [ ] **Step 4: Run the focused backend test and verify GREEN**

Run: `python -m pytest -q gilbic_backend/tests/test_period_close_api_contract.py`

Expected: all tests pass.

- [ ] **Step 5: Commit the backend alias change**

```powershell
git add -- gilbic_backend/src/gilbic_backend/period_close_api.py gilbic_backend/tests/test_period_close_api_contract.py
git commit -m "CB1: expose protected period close to mobile"
```

### Task 2: Add typed Flutter period-close contracts

**Files:**
- Create: `gilbic_mobile/lib/src/core/management/period_close.dart`
- Create: `gilbic_mobile/lib/src/core/management/period_close_repository.dart`
- Create: `gilbic_mobile/test/period_close_repository_test.dart`

**Interfaces:**
- Produces: `PeriodCloseOverview`, `PeriodCloseSummary`, `PeriodCloseItem`, `PeriodClosePermissions`, `PeriodCloseRepository`, and `SpinaPeriodCloseRepository`.
- `PeriodCloseRepository.load(session, deviceId:, status:)` returns the authoritative queue.
- `prepare(session, deviceId:, fiscalPeriodId:)` sends `{"confirm": true}`.
- `post(session, deviceId:, item:, confirmationToken:)` sends the item's exact digest, exact net-income string, account `3100`, and end date.

- [ ] **Step 1: Write failing parsing and request tests**

```dart
test('parses prepared protected close evidence without floating-point math', () async {
  final overview = await repository.load(session, deviceId: 'device-1');
  final item = overview.items.single;
  expect(item.closeStatus, 'prepared_confirmation_required');
  expect(item.netIncome, '60.00');
  expect(item.closeDigest, List<String>.filled(64, 'a').join());
});

test('posts the exact prepared snapshot and confirmation token', () async {
  await repository.post(
    session,
    deviceId: 'device-1',
    item: preparedItem,
    confirmationToken: List<String>.filled(64, 'b').join(),
  );
  expect(decodedBody, {
    'confirm': true,
    'confirmation_token': List<String>.filled(64, 'b').join(),
    'expected_close_digest': List<String>.filled(64, 'a').join(),
    'expected_net_income': '60.00',
    'expected_retained_earnings_account_code': '3100',
    'expected_period_end_date': '2026-08-31',
  });
});
```

- [ ] **Step 2: Run the new repository test and verify RED**

Run: `flutter test test/period_close_repository_test.dart`

Expected: compile failure because the contracts do not exist.

- [ ] **Step 3: Implement strict models and the HTTP adapter**

Keep exact monetary fields as strings. Parse required booleans and identifiers defensively using the existing `spina_api.dart` helpers. Convert network, invalid response, and server detail errors into `SpinaApiException` with period-close-safe wording.

- [ ] **Step 4: Run the repository test and verify GREEN**

Run: `flutter test test/period_close_repository_test.dart`

Expected: all tests pass.

- [ ] **Step 5: Commit typed contracts**

```powershell
git add -- gilbic_mobile/lib/src/core/management/period_close.dart gilbic_mobile/lib/src/core/management/period_close_repository.dart gilbic_mobile/test/period_close_repository_test.dart
git commit -m "CB1: add mobile period close contracts"
```

### Task 3: Build the protected Management period-close page

**Files:**
- Create: `gilbic_mobile/lib/src/features/management/management_period_close_page.dart`
- Create: `gilbic_mobile/test/management_period_close_page_test.dart`
- Modify: `gilbic_mobile/lib/src/features/management/review/management_review.dart`
- Modify: `gilbic_mobile/test/management_review_surface_inventory_test.dart`

**Interfaces:**
- Consumes: `PeriodCloseRepository`, `DeviceIdentityProvider`, `UserSession`, and `showManagementReviewConfirmation`.
- Produces: `ManagementPeriodClosePage` with injectable repository and `String Function()` confirmation-token generator.

- [ ] **Step 1: Write failing widget tests**

Cover these independent behaviors:

```dart
expect(find.byKey(const Key('period-close-summary')), findsOneWidget);
expect(find.text('Server blocker text'), findsOneWidget);
expect(find.byKey(const Key('prepare-period-period-1')), findsOneWidget);
expect(find.byKey(const Key('post-period-period-2')), findsNothing);
```

Then test cancellation causes zero repository writes, confirmed prepare causes one write, posting shows the exact snapshot facts, and a simulated first network failure followed by retry sends the same 64-hex token twice.

- [ ] **Step 2: Run the widget and review-inventory tests and verify RED**

Run: `flutter test test/management_period_close_page_test.dart test/management_review_surface_inventory_test.dart`

Expected: compile/test failure because the page and review surface do not exist.

- [ ] **Step 3: Implement the minimal protected page**

Use one scrollable queue with summary, filter chips, plain status labels, visible blockers, and exact evidence. Add `ManagementMutationSurface.periodClose` with actions `prepare` and `post`. Generate a token once per `fiscalPeriodId:closeDigest`, keep it after uncertain failure, and remove it only after final success or digest change.

- [ ] **Step 4: Run focused page tests and verify GREEN**

Run: `flutter test test/management_period_close_page_test.dart test/management_review_surface_inventory_test.dart`

Expected: all tests pass.

- [ ] **Step 5: Commit the protected page**

```powershell
git add -- gilbic_mobile/lib/src/features/management/management_period_close_page.dart gilbic_mobile/lib/src/features/management/review/management_review.dart gilbic_mobile/test/management_period_close_page_test.dart gilbic_mobile/test/management_review_surface_inventory_test.dart
git commit -m "CB1: add protected mobile period close review"
```

### Task 4: Replace the rejected direct-close action

**Files:**
- Modify: `gilbic_mobile/lib/src/features/management/management_financial_accounting_page.dart`
- Modify: `gilbic_mobile/test/management_financial_accounting_page_test.dart`

**Interfaces:**
- Consumes: `ManagementPeriodClosePage`.
- Produces: a `formal-period-close` launcher and no `period-close-{id}` direct status mutation.

- [ ] **Step 1: Change the existing test to require the protected launcher**

```dart
expect(find.byKey(const Key('formal-period-close')), findsOneWidget);
expect(find.byKey(const Key('period-close-period-aug-2026')), findsNothing);
await tester.tap(find.byKey(const Key('formal-period-close')));
await tester.pumpAndSettle();
expect(find.byType(ManagementPeriodClosePage), findsOneWidget);
```

- [ ] **Step 2: Run the Financial Accounting widget test and verify RED**

Run: `flutter test test/management_financial_accounting_page_test.dart`

Expected: failure because the direct close still exists and the launcher is absent.

- [ ] **Step 3: Add the launcher and remove only the direct close mutation**

Keep **Send to review** and **Reopen**. Remove the `closed` branch from `_changeFiscalPeriodStatus`, stop sending `confirm_close`, and route the new launcher to `ManagementPeriodClosePage`.

- [ ] **Step 4: Run affected Management tests and verify GREEN**

Run: `flutter test test/management_financial_accounting_page_test.dart test/management_dashboard_information_architecture_test.dart test/management_review_test.dart`

Expected: all tests pass.

- [ ] **Step 5: Commit the integration**

```powershell
git add -- gilbic_mobile/lib/src/features/management/management_financial_accounting_page.dart gilbic_mobile/test/management_financial_accounting_page_test.dart
git commit -m "CB1: route fiscal close through protected workflow"
```

### Task 5: Verify and publish the bounded CB1 slice

**Files:**
- Modify only if evidence requires correction: `docs/superpowers/specs/2026-08-30-cb1-mobile-protected-period-close.md`
- Modify only after implementation passes: authoritative GitHub/Notion status records.

**Interfaces:**
- Produces: exact-commit local/CI evidence and a stacked Draft PR based on `codex/ca6-ios-ui-parity`.

- [ ] **Step 1: Run changed backend validation**

Run: `python -m pytest -q gilbic_backend/tests/test_period_close_api_contract.py`

Run: `python -m ruff check gilbic_backend/src/gilbic_backend/period_close_api.py gilbic_backend/tests/test_period_close_api_contract.py`

- [ ] **Step 2: Run focused and complete Flutter validation**

Run: `flutter analyze --fatal-infos`

Run: `flutter test test/period_close_repository_test.dart test/management_period_close_page_test.dart test/management_financial_accounting_page_test.dart test/management_review_surface_inventory_test.dart`

Run: `flutter test`

- [ ] **Step 3: Run complete backend validation**

Run: `python -m pytest -q gilbic_backend/tests`

Expected: no new failure; configured integration skips must be reported, not called passed.

- [ ] **Step 4: Format, diff-check, and review both axes**

Run: `dart format --output=none --set-exit-if-changed gilbic_mobile/lib/src/core/management/period_close.dart gilbic_mobile/lib/src/core/management/period_close_repository.dart gilbic_mobile/lib/src/features/management/management_period_close_page.dart gilbic_mobile/lib/src/features/management/management_financial_accounting_page.dart gilbic_mobile/lib/src/features/management/review/management_review.dart gilbic_mobile/test/period_close_repository_test.dart gilbic_mobile/test/management_period_close_page_test.dart gilbic_mobile/test/management_financial_accounting_page_test.dart gilbic_mobile/test/management_review_surface_inventory_test.dart`

Run: `git diff --check -- <CB1 paths>`

Review Standards and Spec separately. Confirm no SQL/business-rule changes and that the unrelated `architecture-map.json` deletion remains unstaged.

- [ ] **Step 5: Commit documentation, push, and open a stacked Draft PR**

```powershell
git add -- docs/superpowers/specs/2026-08-30-cb1-mobile-protected-period-close.md docs/superpowers/plans/2026-08-30-cb1-mobile-protected-period-close.md
git commit -m "docs: plan protected mobile period close"
git push -u origin codex/cb1-mobile-period-close
gh pr create --draft --base codex/ca6-ios-ui-parity --head codex/cb1-mobile-period-close
```

- [ ] **Step 6: Monitor exact-head CI and update authority records**

Record current implemented behavior, exact test counts, remaining CB1 work, and the no-production/no-merge boundary in Draft PR evidence, Master Issue #296, and SPINA Project Memory. Do not check the whole CB1 box for this bounded workflow.
