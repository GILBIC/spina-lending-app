# Management Employee Activity API and Mobile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give authorized Management users a compact, permission-filtered Employee Activity list and per-Employee timeline in Gilbic Mobile, backed by authoritative PostgreSQL domain evidence and FastAPI.

**Architecture:** A static server registry admits only reviewed activity projections. One read-only PostgreSQL repository derives Employee rows and timeline items from owning-domain records plus allowlisted audit actions, after FastAPI has reduced the caller's permissions to visible domains. Flutter strictly parses and renders the server contract, links to existing protected workflows, and never calculates workflow state or mutates Employee work.

**Tech Stack:** Python 3.11+, FastAPI, psycopg 3, PostgreSQL, pytest, Dart 3.10+, Flutter, `http`, Flutter widget tests.

**Spec:** `docs/superpowers/specs/2026-08-29-management-collector-daily-route-remittance-review-design.md`

## Global Constraints

- This is the first independently reviewable Employee Activity delivery slice: FastAPI, PostgreSQL read projection, and Gilbic Mobile only.
- Do not wire the legacy/local `spina_app` Desktop modules to this feature. Desktop parity requires the separately approved current-Desktop FastAPI shell/migration plan and must consume this same contract later.
- Keep Draft PR #378 Draft, open, unmerged, and undeployed unless a later explicit authorization changes that state.
- Do not access or mutate production data, restart protected services, run a live migration, approve CA2, sign a release, or publish an app.
- Require active identity, active approved device, canonical `management` role, and exact `employee.activity.review` before returning the shell.
- Require the owning-domain view permission for every returned event: `accounting.view`, `support.manage`, or `remittance.view` in the initial registry.
- Seed `employee.activity.review` for Management only. It never implies an owning-domain action permission.
- Initial registered domains are `accounting`, `crm_support`, and `remittance_operations`. Keep `hr`, `payroll`, and `administration` closed domain codes but do not advertise or synthesize them until authoritative source adapters are separately approved.
- Populate rows from active canonical Employee accounts only; do not infer the new model from legacy Desktop roles.
- Hidden domains contribute no rows, counts, timestamps, statuses, navigation targets, or placeholders.
- Use authoritative owning-record state. Never treat free-form `core.audit_logs.details` text as official workflow state.
- Do not return payroll/HR content, government IDs, auth metadata, tokens, raw device identifiers, unrestricted support-message bodies, or unrestricted client documents.
- Do not record keystrokes, screenshots, location, time-on-screen, productivity scores, rankings, or disciplinary conclusions.
- Opening a row or timeline is read-only. Existing owning modules retain maker-checker, self-approval, posting, reversal, correction, and audit rules.
- Use test-first red-green-refactor cycles. Stage only the exact files named by the current task; never use `git add .`, `git add -A`, or `git add --all`.

## File Map

### New backend files

- `gilbic_backend/sql/0109_add_management_employee_activity_permission.sql` — additive permission and canonical Management grant only.
- `gilbic_backend/src/gilbic_backend/management_employee_activity.py` — closed domain/status/activity/navigation codes and immutable response types.
- `gilbic_backend/src/gilbic_backend/management_employee_activity_registry.py` — static reviewed source registry and permission mapping.
- `gilbic_backend/src/gilbic_backend/management_employee_activity_repository.py` — permission-filtered list/timeline PostgreSQL reads and validation.
- `gilbic_backend/src/gilbic_backend/management_employee_activity_api.py` — canonical/mobile GET contracts, auth checks, filters, and safe serialization.
- `gilbic_backend/tests/test_management_employee_activity_migration.py` — migration boundary and idempotency checks.
- `gilbic_backend/tests/test_management_employee_activity_repository.py` — registry, one-query, omission, status, and validation unit contract.
- `gilbic_backend/tests/test_management_employee_activity_postgres.py` — disposable-PostgreSQL source/state/permission-leakage proof.
- `gilbic_backend/tests/test_management_employee_activity_api.py` — role, device, permission, alias, filter, payload, and safe-failure contract.

### Modified backend file

- `gilbic_backend/src/gilbic_backend/main.py` — import and mount the Employee Activity router exactly once.

### New Flutter files

- `gilbic_mobile/lib/src/core/management/management_employee_activity.dart` — strict immutable list/timeline models and closed enums.
- `gilbic_mobile/lib/src/core/management/management_employee_activity_repository.dart` — injectable repository and authenticated HTTP implementation.
- `gilbic_mobile/lib/src/features/management/management_employee_activity_page.dart` — compact Employee rows, filters, refresh, and safe states.
- `gilbic_mobile/lib/src/features/management/management_employee_activity_detail_page.dart` — chronological timeline and authorized owning-record navigation.
- `gilbic_mobile/test/management_employee_activity_repository_test.dart` — strict request/parser tests.
- `gilbic_mobile/test/management_employee_activity_page_test.dart` — permission, layout, filters, stale requests, and navigation tests.

### Modified Flutter files

- `gilbic_mobile/lib/src/features/management/management_dashboard.dart` — add the small `Employee activity` launcher under `People, access & requests` and inject the repository.
- `gilbic_mobile/lib/src/features/dashboard/role_dashboard.dart` — pass optional Employee Activity repository to Management composition.
- `gilbic_mobile/lib/src/features/dashboard/enhanced_role_dashboard.dart` — preserve test composition with the optional repository.
- `gilbic_mobile/test/management_dashboard_information_architecture_test.dart` — prove launcher grouping, permission hiding, and existing-destination preservation.

---

### Task 1: Add the shell permission without new business tables

**Files:**
- Create: `gilbic_backend/sql/0109_add_management_employee_activity_permission.sql`
- Create: `gilbic_backend/tests/test_management_employee_activity_migration.py`

**Interfaces:**
- Consumes: `core.permissions`, `core.roles`, and `core.role_permissions` from the existing authorization schema.
- Produces: exact permission code `employee.activity.review`, granted only to canonical `management`.

- [ ] **Step 1: Write the failing migration contract test**

Assert the migration is transaction-guarded, rerunnable, contains no `CREATE TABLE`, and maps only Management:

```python
def test_employee_activity_migration_is_additive_and_management_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert sql.lstrip().startswith("begin;")
    assert sql.rstrip().endswith("commit;")
    assert "employee.activity.review" in sql
    assert "on conflict" in sql
    assert "create table" not in sql
    assert "('management', 'employee.activity.review')" in sql
    assert "('employee', 'employee.activity.review')" not in sql
    assert "('collector', 'employee.activity.review')" not in sql
    assert "('client', 'employee.activity.review')" not in sql
```

- [ ] **Step 2: Run the migration contract and verify the red state**

Run:

```powershell
python -m pytest -q gilbic_backend/tests/test_management_employee_activity_migration.py
```

Expected: FAIL because migration `0109_add_management_employee_activity_permission.sql` does not exist.

- [ ] **Step 3: Add the idempotent migration**

Use this exact permission mapping and no other schema change:

```sql
BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'employee.activity.review',
    'Review permission-scoped Employee work evidence without gaining domain action authority'
)
ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM (VALUES
    ('management', 'employee.activity.review')
) AS mapping(role_code, permission_code)
JOIN core.roles role ON role.code = mapping.role_code
JOIN core.permissions permission ON permission.code = mapping.permission_code
ON CONFLICT DO NOTHING;

COMMIT;
```

- [ ] **Step 4: Prove the migration contract passes**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit the bounded migration slice**

```powershell
git add -- gilbic_backend/sql/0109_add_management_employee_activity_permission.sql gilbic_backend/tests/test_management_employee_activity_migration.py
git commit -m "feat: seed employee activity review permission"
```

---

### Task 2: Define the closed registry and immutable read contract

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/management_employee_activity.py`
- Create: `gilbic_backend/src/gilbic_backend/management_employee_activity_registry.py`
- Create: `gilbic_backend/tests/test_management_employee_activity_repository.py`

**Interfaces:**
- Consumes: actor permission strings already loaded by `authenticated_device_context`.
- Produces: `EmployeeActivityDomain`, `EmployeeActivityStatus`, `EmployeeActivityCode`, `EmployeeActivityNavigationCode`, `EmployeeActivityRow`, `EmployeeActivityItem`, `EmployeeActivityPage`, `EmployeeActivityTimeline`, and `visible_employee_activity_domains(permissions)`.

- [ ] **Step 1: Write the failing closed-registry tests**

```python
def test_registry_exposes_only_domains_whose_view_permission_is_present() -> None:
    visible = visible_employee_activity_domains(
        frozenset({"employee.activity.review", "accounting.view", "remittance.view"})
    )

    assert [domain.code for domain in visible] == [
        EmployeeActivityDomain.ACCOUNTING,
        EmployeeActivityDomain.REMITTANCE_OPERATIONS,
    ]
    assert all(domain.required_permission != "employee.activity.review" for domain in visible)


def test_unregistered_domains_are_not_advertised() -> None:
    visible = visible_employee_activity_domains(
        frozenset({"employee.activity.review", "accounting.view", "support.manage", "remittance.view"})
    )

    assert EmployeeActivityDomain.HR not in {domain.code for domain in visible}
    assert EmployeeActivityDomain.PAYROLL not in {domain.code for domain in visible}
    assert EmployeeActivityDomain.ADMINISTRATION not in {domain.code for domain in visible}
```

- [ ] **Step 2: Run the registry test and verify the red state**

```powershell
python -m pytest -q gilbic_backend/tests/test_management_employee_activity_repository.py
```

Expected: collection FAIL because the new modules do not exist.

- [ ] **Step 3: Implement exact enums and immutable types**

Define closed values:

```python
class EmployeeActivityDomain(StrEnum):
    ACCOUNTING = "accounting"
    HR = "hr"
    PAYROLL = "payroll"
    CRM_SUPPORT = "crm_support"
    REMITTANCE_OPERATIONS = "remittance_operations"
    ADMINISTRATION = "administration"


class EmployeeActivityStatus(StrEnum):
    NO_ACTIVITY = "no_activity"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    NEEDS_ATTENTION = "needs_attention"


class EmployeeActivityCode(StrEnum):
    ACCOUNTING_JOURNAL_PREPARED = "accounting.journal.prepared"
    SUPPORT_ANSWERED = "support.answered"
    SUPPORT_RESOLVED = "support.resolved"
    REMITTANCE_SUBMITTED = "remittance.submitted"


class EmployeeActivityNavigationCode(StrEnum):
    GENERAL_JOURNALS = "management.general_journals"
    SUPPORT_REQUESTS = "management.support_requests"
    REMITTANCE_REVIEW = "management.remittance_review"
```

`EmployeeActivityItem` must carry `employee_user_id`, `activity_code`, `domain`, `occurred_at`, `business_date`, `record_type`, `record_id`, `display_reference`, `summary`, `workflow_state`, `status`, optional maker/checker display names, and optional navigation code. Bounded strings are validated before serialization.

- [ ] **Step 4: Implement the reviewed initial registry**

Create exactly these registered domain specs:

```python
REGISTERED_EMPLOYEE_ACTIVITY_DOMAINS = (
    EmployeeActivityDomainSpec(
        code=EmployeeActivityDomain.ACCOUNTING,
        required_permission="accounting.view",
        activity_codes=(EmployeeActivityCode.ACCOUNTING_JOURNAL_PREPARED,),
    ),
    EmployeeActivityDomainSpec(
        code=EmployeeActivityDomain.CRM_SUPPORT,
        required_permission="support.manage",
        activity_codes=(
            EmployeeActivityCode.SUPPORT_ANSWERED,
            EmployeeActivityCode.SUPPORT_RESOLVED,
        ),
    ),
    EmployeeActivityDomainSpec(
        code=EmployeeActivityDomain.REMITTANCE_OPERATIONS,
        required_permission="remittance.view",
        activity_codes=(EmployeeActivityCode.REMITTANCE_SUBMITTED,),
    ),
)
```

Do not register HR, Payroll, or Administration in this slice.

- [ ] **Step 5: Run registry tests and verify green**

Run the Step 2 command. Expected: PASS for registry and type tests.

- [ ] **Step 6: Commit the closed contract**

```powershell
git add -- gilbic_backend/src/gilbic_backend/management_employee_activity.py gilbic_backend/src/gilbic_backend/management_employee_activity_registry.py gilbic_backend/tests/test_management_employee_activity_repository.py
git commit -m "feat: define employee activity registry"
```

---

### Task 3: Build the permission-filtered PostgreSQL list and timeline

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/management_employee_activity_repository.py`
- Modify: `gilbic_backend/tests/test_management_employee_activity_repository.py`
- Create: `gilbic_backend/tests/test_management_employee_activity_postgres.py`

**Interfaces:**
- Consumes: `visible_domains: tuple[EmployeeActivityDomainSpec, ...]`, bounded date range, query/status/domain filters, limit, and offset.
- Produces: `PostgresManagementEmployeeActivityRepository.list_employees(...) -> EmployeeActivityPage` and `.load_timeline(...) -> EmployeeActivityTimeline`.

- [ ] **Step 1: Add failing repository tests for one-query reads and hidden-domain omission**

```python
def test_list_employees_uses_one_query_and_passes_only_visible_domain_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor([complete_employee_row()])
    monkeypatch.setattr(repository_module, "open_connection", lambda: FakeConnection(cursor))

    page = PostgresManagementEmployeeActivityRepository().list_employees(
        date_from=date(2026, 8, 29),
        date_to=date(2026, 8, 29),
        visible_domains=registered_domains_for({"accounting.view"}),
        query=None,
        status=None,
        domain=None,
        limit=50,
        offset=0,
    )

    assert cursor.execute_count == 1
    assert page.available_domains == (EmployeeActivityDomain.ACCOUNTING,)
    assert "support.manage" not in repr(cursor.parameters)
    assert "remittance.view" not in repr(cursor.parameters)
```

Add failures for bool-as-count, negative count, naive timestamp, unknown status/activity code, missing Employee UUID, overlong display text, and a requested domain not present in `visible_domains`.

- [ ] **Step 2: Run repository tests and verify red**

```powershell
python -m pytest -q gilbic_backend/tests/test_management_employee_activity_repository.py
```

Expected: FAIL because the repository is not implemented.

- [ ] **Step 3: Implement the repository signatures and validation**

```python
class ManagementEmployeeActivityError(RuntimeError):
    code = "management_employee_activity_unavailable"


class EmployeeActivityNotFound(ManagementEmployeeActivityError):
    code = "employee_activity_not_found"


class PostgresManagementEmployeeActivityRepository:
    def list_employees(
        self,
        *,
        date_from: date,
        date_to: date,
        visible_domains: tuple[EmployeeActivityDomainSpec, ...],
        query: str | None,
        status: EmployeeActivityStatus | None,
        domain: EmployeeActivityDomain | None,
        limit: int,
        offset: int,
    ) -> EmployeeActivityPage: ...

    def load_timeline(
        self,
        *,
        employee_user_id: UUID,
        date_from: date,
        date_to: date,
        visible_domains: tuple[EmployeeActivityDomainSpec, ...],
        domain: EmployeeActivityDomain | None,
        limit: int,
        offset: int,
    ) -> EmployeeActivityTimeline: ...
```

The requested domain must be a member of `visible_domains`; otherwise raise the same authorization-safe error the API maps to 403.

- [ ] **Step 4: Implement a single static SQL projection per read**

Build a static `UNION ALL` event CTE with three adapters:

- `accounting.journal_entries`: activity owner is `created_by_user_id`; state comes from `journal.status`; checker is `posted_by_user_id`; reversal state comes from `reversal_of_entry_id`; summary contains only entry number/reference and safe description.
- `core.audit_logs` allowlisted to `support.answered` and `support.resolved`, joined to `lending.client_support_requests`: activity owner is the audit actor only when that actor has canonical Employee role; state comes from the support record; omit response/message bodies.
- `core.audit_logs` allowlisted to `remittance.submitted`, joined to `lending.collection_remittances`: activity owner is the submitting audit actor only when that actor has canonical Employee role; state comes from the remittance and rejection/receipt evidence; omit photo/device data and itemized client data.

The population CTE must start from active users with canonical Employee role and left-join the visible event CTE. Pass one boolean per registered domain; every adapter begins with its boolean parameter, so a hidden adapter contributes no event before aggregation. Use the same status precedence as the spec:

```sql
case
    when needs_attention_count > 0 then 'needs_attention'
    when awaiting_review_count > 0 then 'awaiting_review'
    when in_progress_count > 0 then 'in_progress'
    when completed_count > 0 then 'completed'
    else 'no_activity'
end
```

Search only normalized Employee display name/username. Parameterize dates, search, status, domain, limit, offset, and Employee UUID. Do not interpolate any client value into SQL.

- [ ] **Step 5: Add disposable PostgreSQL evidence**

Seed active Management/Employee identities and one event in each registered domain. Prove:

```python
def test_hidden_payroll_and_support_domains_leave_no_aggregate_clue(pg_repository) -> None:
    accounting_only = pg_repository.list_employees(
        date_from=BUSINESS_DATE,
        date_to=BUSINESS_DATE,
        visible_domains=registered_domains_for({"accounting.view"}),
        query=None,
        status=None,
        domain=None,
        limit=50,
        offset=0,
    )

    row = next(item for item in accounting_only.rows if item.employee_user_id == EMPLOYEE_ID)
    assert accounting_only.available_domains == (EmployeeActivityDomain.ACCOUNTING,)
    assert row.total_visible_count == 1
    assert row.last_activity_domain == EmployeeActivityDomain.ACCOUNTING
```

Also prove corrected/reversed journals retain both identities without double-counting current state, support text is absent, current remittance state comes from the remittance record, inactive/non-Employee actors do not populate rows, and no read writes an audit or business row.

- [ ] **Step 6: Run repository and disposable PostgreSQL tests**

```powershell
python -m pytest -q gilbic_backend/tests/test_management_employee_activity_repository.py gilbic_backend/tests/test_management_employee_activity_postgres.py
```

Expected: PASS when a disposable test database is configured; PostgreSQL tests may skip only under the repository's existing explicit no-test-database convention and must not be claimed as passed when skipped.

- [ ] **Step 7: Commit the read model**

```powershell
git add -- gilbic_backend/src/gilbic_backend/management_employee_activity_repository.py gilbic_backend/tests/test_management_employee_activity_repository.py gilbic_backend/tests/test_management_employee_activity_postgres.py
git commit -m "feat: derive permission-scoped employee activity"
```

---

### Task 4: Expose canonical and mobile read APIs

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/management_employee_activity_api.py`
- Create: `gilbic_backend/tests/test_management_employee_activity_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/main.py`

**Interfaces:**
- Consumes: authenticated `AccountContext`, registry permission reduction, and repository methods from Task 3.
- Produces: canonical/mobile list and Employee timeline GET routes from the approved spec.

- [ ] **Step 1: Write failing API permission and contract tests**

Test these exact cases:

```python
@pytest.mark.parametrize("path", [
    "/api/v1/management/employee-activity",
    "/api/mobile/v1/management/employee-activity",
])
def test_list_requires_management_role_shell_permission_and_approved_device(path: str) -> None:
    response = client.get(path, headers=authorized_headers())
    assert response.status_code == 200
    assert response.json()["data"]["available_domains"] == ["accounting"]


def test_shell_permission_does_not_reveal_unpermitted_domains() -> None:
    response = client.get(
        "/api/v1/management/employee-activity",
        headers=headers_for_permissions({"employee.activity.review"}),
    )
    assert response.status_code == 200
    assert response.json()["data"]["available_domains"] == []
    assert all(row["total_visible_count"] == 0 for row in response.json()["data"]["rows"])
```

Also test missing bearer token, inactive/unapproved device, non-Management role, missing shell permission, forbidden domain filter, bounded date range, bounded pagination/search, alias equality, 404 for inactive/non-Employee detail target, safe 503, and absence of protected fields.

- [ ] **Step 2: Run API tests and verify red**

```powershell
python -m pytest -q gilbic_backend/tests/test_management_employee_activity_api.py
```

Expected: FAIL because the router is not mounted.

- [ ] **Step 3: Implement authentication and filter boundaries**

Use `authenticated_device_context`, then require both:

```python
if "management" not in actor.roles:
    raise HTTPException(status_code=403, detail={
        "code": "management_role_required",
        "message": "Management access is required for Employee Activity.",
    })
if "employee.activity.review" not in actor.permissions:
    raise HTTPException(status_code=403, detail={
        "code": "employee_activity_permission_required",
        "message": "Employee Activity review permission is required.",
    })
```

Default `date_from` and `date_to` to the current Asia/Manila business date. Reject `date_from > date_to`, ranges over 31 days, `q` over 100 normalized characters, `limit` outside 1–100, negative offset, and domain filters not included by `visible_employee_activity_domains(actor.permissions)`.

- [ ] **Step 4: Serialize the strict response contract**

List response keys are `date_from`, `date_to`, `generated_at`, `available_domains`, and `rows`. Each row contains `employee_user_id`, `employee_name`, `function_labels`, four visible workflow counts, `total_visible_count`, optional last-visible timestamp/domain, `status`, and `status_message`.

Timeline response contains the same range/domain metadata, Employee identity, and `items`. Each item contains only the approved immutable fields and optional navigation metadata. Serialize timestamps with offsets and dates as ISO strings.

- [ ] **Step 5: Mount exactly one router and prove green**

Import `create_management_employee_activity_router` in `main.py` and mount it beside the other Management routers. Run:

```powershell
python -m pytest -q gilbic_backend/tests/test_management_employee_activity_api.py gilbic_backend/tests/test_app.py
```

Expected: PASS and exactly one canonical OpenAPI entry for each route; mobile aliases remain excluded from generated schema.

- [ ] **Step 6: Commit the API slice**

```powershell
git add -- gilbic_backend/src/gilbic_backend/management_employee_activity_api.py gilbic_backend/tests/test_management_employee_activity_api.py gilbic_backend/src/gilbic_backend/main.py
git commit -m "feat: expose management employee activity reads"
```

---

### Task 5: Add strict Flutter models and authenticated repository

**Files:**
- Create: `gilbic_mobile/lib/src/core/management/management_employee_activity.dart`
- Create: `gilbic_mobile/lib/src/core/management/management_employee_activity_repository.dart`
- Create: `gilbic_mobile/test/management_employee_activity_repository_test.dart`

**Interfaces:**
- Consumes: canonical JSON from Task 4, existing authenticated HTTP/session/device conventions.
- Produces: `ManagementEmployeeActivityRepository.listEmployees(...)` and `.loadTimeline(...)` with immutable Dart models.

- [ ] **Step 1: Write failing parser/request tests**

```dart
test('omitted domains remain absent and are not synthesized as zero', () async {
  final page = ManagementEmployeeActivityPage.fromPayload(successPayload(
    availableDomains: const ['accounting'],
    rows: const [accountingOnlyRow],
  ));

  expect(page.availableDomains, [ManagementEmployeeActivityDomain.accounting]);
  expect(page.availableDomains, isNot(contains(ManagementEmployeeActivityDomain.payroll)));
  expect(page.rows.single.totalVisibleCount, 1);
});
```

Add fail-closed cases for unknown status/activity/domain/navigation codes, negative/non-integer counts, naive timestamps, invalid UUID/date, overlong strings, missing fields, non-list rows/items, and malformed success envelopes. Prove requests include bearer and device headers and URL-encode filters.

- [ ] **Step 2: Run the repository test and verify red**

```powershell
flutter test test/management_employee_activity_repository_test.dart
```

Run from `gilbic_mobile`. Expected: FAIL because the models/repository do not exist.

- [ ] **Step 3: Implement closed enums and strict parsers**

Use enhanced enums with exact wire values for the six domain codes, five statuses, four initial activity codes, and three navigation codes. Reject unknown values with `FormatException`; do not map them to generic activity. Preserve all server counts/statuses without recomputation.

- [ ] **Step 4: Implement the injectable HTTP repository**

```dart
abstract interface class ManagementEmployeeActivityRepository {
  Future<ManagementEmployeeActivityPage> listEmployees({
    required DateTime dateFrom,
    required DateTime dateTo,
    String? query,
    ManagementEmployeeActivityDomain? domain,
    ManagementEmployeeActivityStatus? status,
    int limit = 50,
    int offset = 0,
  });

  Future<ManagementEmployeeActivityTimeline> loadTimeline({
    required String employeeUserId,
    required DateTime dateFrom,
    required DateTime dateTo,
    ManagementEmployeeActivityDomain? domain,
    int limit = 100,
    int offset = 0,
  });
}
```

Follow existing Management repositories for base URL, token, `X-Device-Id`, 401/403 classification, and safe unavailable errors. Do not cache responses across sessions.

- [ ] **Step 5: Run parser/repository tests and commit**

```powershell
flutter test test/management_employee_activity_repository_test.dart
dart format --set-exit-if-changed lib/src/core/management/management_employee_activity.dart lib/src/core/management/management_employee_activity_repository.dart test/management_employee_activity_repository_test.dart
```

Expected: PASS and format clean.

```powershell
git add -- gilbic_mobile/lib/src/core/management/management_employee_activity.dart gilbic_mobile/lib/src/core/management/management_employee_activity_repository.dart gilbic_mobile/test/management_employee_activity_repository_test.dart
git commit -m "feat: add employee activity mobile contract"
```

---

### Task 6: Add compact Management rows and read-only timeline navigation

**Files:**
- Create: `gilbic_mobile/lib/src/features/management/management_employee_activity_page.dart`
- Create: `gilbic_mobile/lib/src/features/management/management_employee_activity_detail_page.dart`
- Create: `gilbic_mobile/test/management_employee_activity_page_test.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_dashboard.dart`
- Modify: `gilbic_mobile/lib/src/features/dashboard/role_dashboard.dart`
- Modify: `gilbic_mobile/lib/src/features/dashboard/enhanced_role_dashboard.dart`
- Modify: `gilbic_mobile/test/management_dashboard_information_architecture_test.dart`

**Interfaces:**
- Consumes: repository/models from Task 5 and existing Management page destinations for general journals, support requests, and remittance review.
- Produces: permission-gated dashboard launcher, compact Employee rows, timeline filters, and authorized navigation only.

- [ ] **Step 1: Write failing dashboard and page tests**

Prove the launcher is inside `People, access & requests`, is absent without exact permission, and opens the page with no write. Add a 360 × 640, 1.3× text test whose row finds these semantics without overflow:

```dart
expect(find.text('Employee Name · Accounting'), findsOneWidget);
expect(find.textContaining('6 completed'), findsOneWidget);
expect(find.textContaining('1 awaiting Management'), findsOneWidget);
expect(find.textContaining('needs attention'), findsOneWidget);
expect(tester.takeException(), isNull);
```

Also test loading, empty permitted activity, shell-with-zero-visible-domains, 401/403, unavailable, refresh, date/domain/status/search filters, stale response suppression, timeline order, safe unknown destination, owning-page navigation, enlarged text, and no mutation call.

- [ ] **Step 2: Run widget tests and verify red**

```powershell
flutter test test/management_employee_activity_page_test.dart test/management_dashboard_information_architecture_test.dart
```

Expected: FAIL because the launcher/pages do not exist.

- [ ] **Step 3: Add the small permission-gated launcher**

Add `Employee activity` under `People, access & requests` with icon `Icons.manage_search_outlined`, description `Review authorized Employee work, approvals, and exceptions`, exact permission `employee.activity.review`, and a distinct `_ManagementAction.employeeActivity`. Do not enlarge or replace the section.

- [ ] **Step 4: Implement the compact list page**

Use one tap target per Employee with at least 48 logical pixels. Render Employee/function, the server's visible counts/status, and last visible activity. Show `No permitted activity in this range` exactly for `no_activity`; never say the Employee did no work. Filters trigger a new request-generation token so late responses cannot replace current filters.

- [ ] **Step 5: Implement the read-only timeline and navigation map**

Render time, domain, summary/reference, workflow state, evidence labels, maker/checker attribution, and status. Map only:

```dart
switch (item.navigationCode) {
  case ManagementEmployeeActivityNavigationCode.generalJournals:
    openGeneralJournal(item.recordId);
  case ManagementEmployeeActivityNavigationCode.supportRequests:
    openSupportRequests(item.recordId);
  case ManagementEmployeeActivityNavigationCode.remittanceReview:
    openRemittanceReview(item.recordId);
  case null:
    showReadOnlyDetailUnavailable();
}
```

The destination reuses its own repository and permission checks. Do not add approve, reject, post, reverse, edit, or impersonate buttons to Employee Activity.

- [ ] **Step 6: Run focused and complete Flutter checks**

```powershell
flutter test test/management_employee_activity_repository_test.dart test/management_employee_activity_page_test.dart test/management_dashboard_information_architecture_test.dart
flutter analyze --fatal-infos
flutter test
```

Expected: all focused tests, analyzer, and complete suite PASS.

- [ ] **Step 7: Format and commit the Management UI slice**

```powershell
dart format --set-exit-if-changed lib/src/features/management/management_employee_activity_page.dart lib/src/features/management/management_employee_activity_detail_page.dart lib/src/features/management/management_dashboard.dart lib/src/features/dashboard/role_dashboard.dart lib/src/features/dashboard/enhanced_role_dashboard.dart test/management_employee_activity_page_test.dart test/management_dashboard_information_architecture_test.dart
git add -- gilbic_mobile/lib/src/features/management/management_employee_activity_page.dart gilbic_mobile/lib/src/features/management/management_employee_activity_detail_page.dart gilbic_mobile/test/management_employee_activity_page_test.dart gilbic_mobile/lib/src/features/management/management_dashboard.dart gilbic_mobile/lib/src/features/dashboard/role_dashboard.dart gilbic_mobile/lib/src/features/dashboard/enhanced_role_dashboard.dart gilbic_mobile/test/management_dashboard_information_architecture_test.dart
git commit -m "feat: add management employee activity review"
```

---

### Task 7: Exact-head verification and guarded handoff

**Files:**
- Modify only if evidence reveals a defect: files already owned by Tasks 1–6.

**Interfaces:**
- Consumes: the complete slice and exact Git head.
- Produces: review evidence; no merge, deployment, protected database write, or release.

- [ ] **Step 1: Run backend focused and complete checks**

```powershell
python -m pytest -q gilbic_backend/tests/test_management_employee_activity_migration.py gilbic_backend/tests/test_management_employee_activity_repository.py gilbic_backend/tests/test_management_employee_activity_api.py gilbic_backend/tests/test_management_employee_activity_postgres.py
python -m pytest -q gilbic_backend/tests
```

Record passed and skipped totals separately; never report skipped PostgreSQL tests as passed.

- [ ] **Step 2: Run backend static checks on changed Python files**

```powershell
python -m ruff check gilbic_backend/src/gilbic_backend/management_employee_activity.py gilbic_backend/src/gilbic_backend/management_employee_activity_registry.py gilbic_backend/src/gilbic_backend/management_employee_activity_repository.py gilbic_backend/src/gilbic_backend/management_employee_activity_api.py gilbic_backend/tests/test_management_employee_activity_migration.py gilbic_backend/tests/test_management_employee_activity_repository.py gilbic_backend/tests/test_management_employee_activity_api.py gilbic_backend/tests/test_management_employee_activity_postgres.py
python -m ruff format --check gilbic_backend/src/gilbic_backend/management_employee_activity.py gilbic_backend/src/gilbic_backend/management_employee_activity_registry.py gilbic_backend/src/gilbic_backend/management_employee_activity_repository.py gilbic_backend/src/gilbic_backend/management_employee_activity_api.py gilbic_backend/tests/test_management_employee_activity_migration.py gilbic_backend/tests/test_management_employee_activity_repository.py gilbic_backend/tests/test_management_employee_activity_api.py gilbic_backend/tests/test_management_employee_activity_postgres.py
```

Expected: no Ruff errors and formatting unchanged.

- [ ] **Step 3: Run complete Flutter verification**

```powershell
flutter analyze --fatal-infos
flutter test
```

Expected: analyzer and suite PASS.

- [ ] **Step 4: Prove documentation/worktree consistency**

```powershell
git diff --check
git status --short --branch
git rev-parse HEAD
```

Expected: no whitespace errors; only intentionally uncommitted evidence files, if any, are reported. Do not stage generated APKs, build trees, auth files, environment files, or local database artifacts.

- [ ] **Step 5: Update Draft PR evidence without changing its state**

Post the exact head, focused/full test totals, skipped totals, analyzer result, permission/privacy proof, and remaining Desktop/HR/Payroll/Administration gates to Draft PR #378. Keep it Draft and unmerged.

## Self-Review Record

- Spec coverage in this plan: Employee Activity shell permission; static registered projections; permission-filtered Employee rows and timeline; Accounting/support/remittance initial evidence; maker-checker attribution; strict API aliases; compact Mobile UX; safe navigation; failure/privacy tests; guarded exact-head evidence.
- Deliberately separate dependent work: Collector daily-route/remittance implementation, client-row implementation, HR source adapter, Payroll source adapter, Administration source adapter, and current SPINA Desktop FastAPI UI parity. These require their own independently reviewable plans; none may reuse the legacy/local Desktop as a second authority.
- Placeholder scan: every task names its files, interfaces, test command, expected result, implementation boundary, and commit scope.
- Type consistency: backend and Dart contracts use the same six domain codes, five status codes, four initial activity codes, three navigation codes, and exact permission names.
