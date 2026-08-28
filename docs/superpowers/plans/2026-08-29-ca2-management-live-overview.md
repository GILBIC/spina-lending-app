# CA2 Live Management Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a server-authoritative, permission-filtered live Management overview to Gilbic Mobile while preserving all existing Management launchers and keeping Desktop/mobile capability definitions aligned.

**Architecture:** A new FastAPI router authenticates an approved Management device, requires `management.dashboard.view`, and asks one PostgreSQL repository method for one statement-level aggregate snapshot. Flutter strictly parses the stable metric-key contract, renders live facts and permitted attention queues above the existing launcher hierarchy, and maps every known metric back to an existing protected workflow without calculating official values locally.

**Tech Stack:** Python 3.11+, FastAPI, psycopg 3, PostgreSQL, pytest, Dart 3.10+, Flutter, `http`, Flutter widget tests.

**Spec:** `docs/superpowers/specs/2026-08-29-ca2-management-live-overview-design.md`

## Global Constraints

- Start from exact reviewed commit `cab5737bce8a8d79e052dda9149f3e5cee162e4b` plus the committed design at `26ad6170` on `codex/ca2-management-live-overview`.
- Keep the implementation stacked on Draft PR #376; do not merge, deploy, restart a protected service, sign/store-release an app, or mutate a protected/live database.
- Add no SQL migration, materialized view, cache table, trigger, scheduled refresh, or second dashboard ledger.
- FastAPI is the only application-data boundary; Supabase Auth proves identity and PostgreSQL remains authoritative for roles, permissions, loans, balances, collections, requests, devices, and notifications.
- Require both canonical `management` role and exact `management.dashboard.view` permission after active-device authentication.
- Execute exactly one parameterized PostgreSQL statement for each successful overview request.
- Return common metrics to every authorized Management actor and omit unauthorized specialized metrics entirely; never zero-fill, null-fill, or label a hidden queue.
- Return aggregate facts only; never include names, user IDs, client IDs, receipt numbers, support text, request notes, or raw/hashed device identifiers.
- Serialize all PHP amounts as nonnegative fixed two-decimal strings; never serialize money as JSON floating point.
- Flutter may format server values for display but may not calculate official totals, invent thresholds, infer hidden queues, or persist a snapshot across a new dashboard/session.
- Existing launcher groups and destinations remain usable when overview loading fails.
- Desktop and mobile have functional Management/Employee capability parity over the roadmap: layouts may differ, but role, permission, maker-checker, backend rule, official record, and outcome meanings may not diverge.
- Use strict red-green-refactor cycles and stage only files named by the current task. Never use `git add .` or `git add -A`.

## File Map

### New backend files

- `gilbic_backend/src/gilbic_backend/management_dashboard_overview_repository.py` — immutable snapshot types, metric constants, one-statement PostgreSQL aggregate, validation, and permission-driven omission.
- `gilbic_backend/src/gilbic_backend/management_dashboard_overview_api.py` — canonical/mobile GET routes, role/permission checks, safe serialization, and unavailable-error translation.
- `gilbic_backend/tests/test_management_dashboard_overview_repository.py` — unit contract for one execute call, metric order, omission, and invalid-value handling.
- `gilbic_backend/tests/test_management_dashboard_overview_postgres.py` — disposable-PostgreSQL proof of counts, money, actor scoping, exclusions, and no writes.
- `gilbic_backend/tests/test_management_dashboard_overview_api.py` — authentication context, role/permission matrix, path aliases, payload shape, and safe failures.

### Modified backend file

- `gilbic_backend/src/gilbic_backend/main.py` — import and mount the new router exactly once beside the other Management routers.

### New Flutter files

- `gilbic_mobile/lib/src/core/management/management_dashboard_overview.dart` — strict immutable response model, known-key enum, decimal-string validation, and ignored-future-key diagnostics.
- `gilbic_mobile/lib/src/core/management/management_dashboard_overview_repository.dart` — injectable interface and authenticated HTTP implementation.
- `gilbic_mobile/test/management_dashboard_overview_repository_test.dart` — exact request contract and fail-closed parser coverage.
- `gilbic_mobile/test/management_dashboard_live_overview_test.dart` — loading, success, zero, omission, failure, refresh, stale-response, navigation, and small-screen widget coverage.

### Modified Flutter files

- `gilbic_mobile/lib/src/features/management/management_dashboard.dart` — stateful live overview region, request-generation guard, refresh/retry UI, key-to-destination mapping, and unchanged launcher hierarchy.
- `gilbic_mobile/lib/src/features/dashboard/role_dashboard.dart` — optional overview-repository injection passed to Management.
- `gilbic_mobile/lib/src/features/dashboard/enhanced_role_dashboard.dart` — optional overview-repository injection for composition/widget tests.
- `gilbic_mobile/test/management_dashboard_information_architecture_test.dart` — inject a deterministic overview fake and prove all existing sections/destinations remain reachable.

### Authoritative documentation

- `README.md` — state that Management/Employee Desktop and mobile share one capability/permission model and one FastAPI authority.
- `docs/architecture/system-map.md` — distinguish current implemented surfaces from intended cross-platform capability parity and record the live overview boundary.
- `docs/architecture/progress-map.md` — add a supersession note so its archived V1.1 mobile-scope assumption cannot be mistaken for the current Management decision.

---

### Task 1: One-statement PostgreSQL overview repository

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/management_dashboard_overview_repository.py`
- Create: `gilbic_backend/tests/test_management_dashboard_overview_repository.py`
- Create: `gilbic_backend/tests/test_management_dashboard_overview_postgres.py`

**Interfaces:**
- Consumes: `open_connection()` from `gilbic_backend.database` and authenticated application `actor_user_id: UUID` supplied later by the API.
- Produces: `ManagementDashboardMetric`, `ManagementDashboardOverview`, `ManagementDashboardOverviewError`, and `PostgresManagementDashboardOverviewRepository.load_overview` returning `ManagementDashboardOverview`.

- [ ] **Step 1: Write the failing repository contract test**

Create a fake connection/cursor that returns one complete row and counts calls to `execute`. Assert exact metric order, permission omission, actor argument, and the one-statement rule:

```python
def test_load_overview_uses_one_statement_and_omits_unpermitted_queues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor(_complete_snapshot_row())
    monkeypatch.setattr(
        overview_repository,
        "open_connection",
        lambda: FakeConnection(cursor),
    )

    result = PostgresManagementDashboardOverviewRepository().load_overview(
        actor_user_id=ACTOR_USER_ID,
        include_remittances=False,
        include_renewals=True,
        include_accounts=False,
        include_devices=True,
        include_support=False,
    )

    assert cursor.execute_count == 1
    assert cursor.parameters == (
        False,
        False,
        ACTOR_USER_ID,
        True,
        False,
        False,
        True,
        False,
        ACTOR_USER_ID,
    )
    assert [metric.key for metric in result.metrics] == [
        "portfolio.active_clients",
        "portfolio.active_loans",
        "portfolio.overdue_loans",
        "portfolio.outstanding_balance",
        "collections.latest_day",
        "collections.unremitted",
        "queues.renewals_protected",
        "queues.collector_mobile_devices",
        "activity.unread",
    ]
    assert "queues.remittances_assigned" not in {
        metric.key for metric in result.metrics
    }
```

Also add parameterized failures for a negative count, negative amount, missing row, naive `generated_at`, and a non-`Decimal` money value. Each must raise `ManagementDashboardOverviewError` and expose no raw database text.

- [ ] **Step 2: Run the repository test and verify the red state**

Run:

```powershell
python -m pytest -q gilbic_backend/tests/test_management_dashboard_overview_repository.py
```

Expected: collection fails because `management_dashboard_overview_repository` does not exist.

- [ ] **Step 3: Add the immutable repository interface and validation**

Define these exact types and signature:

```python
@dataclass(frozen=True, slots=True)
class ManagementDashboardMetric:
    key: str
    count: int | None = None
    amount: Decimal | None = None
    as_of_date: date | None = None


@dataclass(frozen=True, slots=True)
class ManagementDashboardOverview:
    generated_at: datetime
    metrics: tuple[ManagementDashboardMetric, ...]


class ManagementDashboardOverviewError(RuntimeError):
    code = "management_overview_unavailable"


class PostgresManagementDashboardOverviewRepository:
    def load_overview(
        self,
        *,
        actor_user_id: UUID,
        include_remittances: bool,
        include_renewals: bool,
        include_accounts: bool,
        include_devices: bool,
        include_support: bool,
    ) -> ManagementDashboardOverview:
        raise NotImplementedError
```

Use private constructors `_count_metric`, `_amount_metric`, and `_combined_metric` that reject bool-as-int, negative values, missing values, and negative money before a metric reaches the API.

- [ ] **Step 4: Implement the single parameterized SQL statement**

Use one `cursor.execute` call with CTEs named `portfolio`, `latest_collection`, `collections`, `remittances`, `renewals`, `registrations`, `collector_devices`, `support`, and `activity`. The statement must preserve these predicates:

```sql
with portfolio as (
    select
        count(*) filter (
            where lower(loan.status) = 'active'
        ) as active_loan_count,
        count(distinct loan.client_id) filter (
            where lower(loan.status) = 'active'
        ) as active_client_count,
        count(*) filter (
            where lower(loan.status) = 'active'
              and loan.due_date < current_date
              and coalesce(state.remaining_balance, loan.principal) > 0
        ) as overdue_loan_count,
        coalesce(sum(
            coalesce(state.remaining_balance, loan.principal)
        ) filter (
            where lower(loan.status) = 'active'
        ), 0)::numeric(18,2) as outstanding_balance
    from lending.loans loan
    left join lending.loan_collection_state state on state.loan_id = loan.id
),
latest_collection as (
    select max(collection_date) as collection_date
    from lending.collection_transactions
    where is_voided = false
),
collections as (
    select
        latest.collection_date,
        count(*) filter (
            where transaction.is_voided = false
              and transaction.entry_type <> 'pass'
              and transaction.collection_date = latest.collection_date
        ) as latest_count,
        coalesce(sum(transaction.amount) filter (
            where transaction.is_voided = false
              and transaction.entry_type <> 'pass'
              and transaction.collection_date = latest.collection_date
        ), 0)::numeric(18,2) as latest_amount,
        count(*) filter (
            where transaction.is_voided = false
              and transaction.is_locked = false
              and transaction.remittance_id is null
        ) as unremitted_count,
        coalesce(sum(transaction.amount) filter (
            where transaction.is_voided = false
              and transaction.is_locked = false
              and transaction.remittance_id is null
              and transaction.entry_type <> 'pass'
        ), 0)::numeric(18,2) as unremitted_amount
    from latest_collection latest
    left join lending.collection_transactions transaction on true
    group by latest.collection_date
),
remittances as (
    select
        case when %s then count(*) else null end as item_count,
        case when %s then coalesce(sum(remittance.total_amount), 0) else null end
            ::numeric(18,2) as total_amount
    from lending.collection_remittances remittance
    where remittance.recipient_user_id = %s
      and remittance.status = 'submitted'
      and remittance.received_at is null
      and not exists (
          select 1
          from lending.collection_remittance_rejections rejection
          where rejection.remittance_id = remittance.id
      )
),
renewals as (
    select case when %s then count(*) else null end as item_count
    from lending.client_renewal_requests request
    where request.status = 'pending'
),
registrations as (
    select
        case when %s then (
            select count(distinct account.id)
            from core.users account
            join core.user_roles user_role on user_role.user_id = account.id
            join core.roles role on role.id = user_role.role_id
            where account.status = 'pending'
              and role.code in ('collector', 'employee', 'management')
        ) else null end as staff_count,
        case when %s then (
            select count(*)
            from core.client_registration_requests request
            where request.status = 'pending'
        ) else null end as client_count
),
collector_devices as (
    select case when %s then count(distinct device.id) else null end as item_count
    from core.devices device
    join core.user_roles user_role on user_role.user_id = device.user_id
    join core.roles role on role.id = user_role.role_id
    where role.code = 'collector'
      and device.status = 'pending'
      and lower(device.platform) in ('android', 'ios')
),
support as (
    select case when %s then count(*) else null end as item_count
    from lending.client_support_requests request
    where request.status in ('open', 'answered')
),
activity as (
    select count(*) as item_count
    from core.activity_notifications notification
    where notification.recipient_user_id = %s
      and notification.is_read = false
)
select
    statement_timestamp() as generated_at,
    portfolio.*,
    collections.*,
    remittances.item_count as remittance_count,
    remittances.total_amount as remittance_amount,
    renewals.item_count as renewal_count,
    registrations.staff_count,
    registrations.client_count,
    collector_devices.item_count as collector_device_count,
    support.item_count as support_count,
    activity.item_count as unread_activity_count
from portfolio
cross join collections
cross join remittances
cross join renewals
cross join registrations
cross join collector_devices
cross join support
cross join activity
```

Use the exact parameter order:

```python
(
    include_remittances,
    include_remittances,
    actor_user_id,
    include_renewals,
    include_accounts,
    include_accounts,
    include_devices,
    include_support,
    actor_user_id,
)
```

The fake-cursor test must retain this nine-value order. Construct metrics in the fixed order from the spec. Add the two `account.manage` metrics together, and omit a specialized metric unless its input flag is true and the row value is non-null.

- [ ] **Step 5: Run the repository unit test to green**

Run:

```powershell
python -m pytest -q gilbic_backend/tests/test_management_dashboard_overview_repository.py
```

Expected: all repository contract and validation tests pass.

- [ ] **Step 6: Write the failing disposable-PostgreSQL integration test**

Follow the existing `GILBIC_TEST_DATABASE_URL` skip pattern. Seed uniquely named users/roles/devices, clients/loans/state, current and prior collection transactions including PASS/void/locked/remitted variants, actor/other-recipient remittances including a rejection, pending/finished renewals, pending staff/client registrations, open/answered/resolved support, and actor/other/read activity notifications.

The central assertion must be:

```python
overview = PostgresManagementDashboardOverviewRepository().load_overview(
    actor_user_id=case.actor_user_id,
    include_remittances=True,
    include_renewals=True,
    include_accounts=True,
    include_devices=True,
    include_support=True,
)
metrics = {metric.key: metric for metric in overview.metrics}

assert metrics["portfolio.active_clients"].count == 1
assert metrics["portfolio.active_loans"].count == 2
assert metrics["portfolio.overdue_loans"].count == 1
assert metrics["portfolio.outstanding_balance"].amount == Decimal("7900.00")
assert metrics["collections.latest_day"].count == 2
assert metrics["collections.latest_day"].amount == Decimal("150.00")
assert metrics["collections.unremitted"].count == 3
assert metrics["collections.unremitted"].amount == Decimal("150.00")
assert metrics["queues.remittances_assigned"].count == 1
assert metrics["queues.remittances_assigned"].amount == Decimal("125.00")
assert metrics["queues.renewals_protected"].count == 1
assert metrics["queues.staff_registrations"].count == 1
assert metrics["queues.client_registrations"].count == 1
assert metrics["queues.collector_mobile_devices"].count == 2
assert metrics["queues.borrower_support"].count == 2
assert metrics["activity.unread"].count == 1
```

Take a before/after count of `core.audit_logs` and every seeded business table and assert the overview read writes nothing. Cleanup by exact seeded UUIDs in foreign-key-safe order.

- [ ] **Step 7: Run disposable PostgreSQL coverage**

Run:

```powershell
python -m pytest -q gilbic_backend/tests/test_management_dashboard_overview_postgres.py
```

Expected: PASS when `GILBIC_TEST_DATABASE_URL` is configured; otherwise one explicit skip that must remain recorded as an open evidence gate.

- [ ] **Step 8: Commit the repository slice**

```powershell
git add -- gilbic_backend/src/gilbic_backend/management_dashboard_overview_repository.py gilbic_backend/tests/test_management_dashboard_overview_repository.py gilbic_backend/tests/test_management_dashboard_overview_postgres.py
git diff --cached --check
git commit -m "feat: add management overview snapshot"
```

### Task 2: Protected FastAPI overview contract

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/management_dashboard_overview_api.py`
- Create: `gilbic_backend/tests/test_management_dashboard_overview_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/main.py`

**Interfaces:**
- Consumes: `PostgresManagementDashboardOverviewRepository.load_overview` from Task 1 and `authenticated_device_context`.
- Produces: `management_dashboard_overview_repository_dependency()` and `create_management_dashboard_overview_router()` with canonical/mobile GET routes.

- [ ] **Step 1: Write failing API role, permission, and alias tests**

Build `FakeAuthClient`, `FakeAccounts`, and `FakeOverviewRepository` using the pattern in `test_management_loan_api.py`. `FakeAccounts` accepts independent `roles` and `permissions` so tests prove:

```python
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/management/dashboard-overview",
        "/api/mobile/v1/management/dashboard-overview",
    ],
)
def test_management_overview_aliases_return_the_same_filtered_shape(path: str) -> None:
    client, repository = client_with_fakes(
        roles=("management",),
        permissions=(
            "management.dashboard.view",
            "remittance.receive",
            "account.manage",
        ),
    )

    response = client.get(path, headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "generated_at": "2026-08-29T04:15:30+00:00",
            "currency": "PHP",
            "metrics": EXPECTED_METRICS,
        },
    }
    assert repository.arguments.include_remittances is True
    assert repository.arguments.include_renewals is False
    assert repository.arguments.include_accounts is True
```

Add separate tests for non-Management with permission, Management without dashboard permission, missing device header, unauthorized specialized omission, fixed money strings, optional `as_of_date`, repository failure -> safe 503, and POST -> 405.

- [ ] **Step 2: Run the API test and verify the red state**

Run:

```powershell
python -m pytest -q gilbic_backend/tests/test_management_dashboard_overview_api.py
```

Expected: collection fails because the API module and router registration do not exist.

- [ ] **Step 3: Implement the protected router and serializer**

Use this control flow:

```python
actor = authenticated_device_context(
    authorization=authorization,
    device_identifier=x_device_id,
    auth=auth,
    accounts=accounts,
)
if "management" not in actor.roles:
    raise HTTPException(
        status_code=403,
        detail={
            "code": "management_role_required",
            "message": "Management access is required for the live overview.",
        },
    )
if "management.dashboard.view" not in actor.permissions:
    raise HTTPException(
        status_code=403,
        detail={
            "code": "management_dashboard_permission_required",
            "message": "Management dashboard permission is required.",
        },
    )
```

Call `load_overview` with `actor.user_id` and flags derived only from `actor.permissions`. Serialize count only when non-null, amount with:

```python
def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")
```

Serialize `as_of_date` only when present. Catch `ManagementDashboardOverviewError` and `psycopg.Error`, then return HTTP 503 with:

```python
{
    "code": "management_overview_unavailable",
    "message": "The live Management overview is temporarily unavailable.",
}
```

Do not log or include the caught exception text in the HTTP response.

- [ ] **Step 4: Register the router exactly once**

Add one import and one include next to the existing Management routers:

```python
from .management_dashboard_overview_api import (
    create_management_dashboard_overview_router,
)

# inside create_app(), after create_management_router()
app.include_router(create_management_dashboard_overview_router())
```

- [ ] **Step 5: Run focused backend tests**

Run:

```powershell
python -m pytest -q gilbic_backend/tests/test_management_dashboard_overview_api.py gilbic_backend/tests/test_management_dashboard_overview_repository.py gilbic_backend/tests/test_management_loan_api.py gilbic_backend/tests/test_management_operations_api.py gilbic_backend/tests/test_activity_notification_api.py gilbic_backend/tests/test_remittance_api.py gilbic_backend/tests/test_renewal_api.py gilbic_backend/tests/test_support_api.py
```

Expected: all tests pass; route aliases and existing protected APIs do not regress.

- [ ] **Step 6: Commit the API slice**

```powershell
git add -- gilbic_backend/src/gilbic_backend/management_dashboard_overview_api.py gilbic_backend/src/gilbic_backend/main.py gilbic_backend/tests/test_management_dashboard_overview_api.py
git diff --cached --check
git commit -m "feat: expose protected management overview"
```

### Task 3: Strict Flutter overview model and HTTP repository

**Files:**
- Create: `gilbic_mobile/lib/src/core/management/management_dashboard_overview.dart`
- Create: `gilbic_mobile/lib/src/core/management/management_dashboard_overview_repository.dart`
- Create: `gilbic_mobile/test/management_dashboard_overview_repository_test.dart`

**Interfaces:**
- Consumes: `UserSession`, exact device ID string, `ApiConfig.endpoint`, and `spina_api.dart` response helpers.
- Produces: `ManagementDashboardMetricKey`, `ManagementDashboardMetric`, `ManagementDashboardOverview`, `ManagementDashboardOverviewRepository.loadOverview`, and `SpinaManagementDashboardOverviewRepository`.

- [ ] **Step 1: Write the failing exact-request and happy-path parser test**

```dart
test('loads the protected mobile overview with bearer and device headers', () async {
  late http.Request captured;
  final repository = SpinaManagementDashboardOverviewRepository(
    client: MockClient((request) async {
      captured = request;
      return http.Response(jsonEncode(_successPayload), 200);
    }),
  );

  final overview = await repository.loadOverview(
    _session,
    deviceId: 'management-phone',
  );

  expect(captured.method, 'GET');
  expect(
    captured.url.path,
    '/api/mobile/v1/management/dashboard-overview',
  );
  expect(captured.headers['authorization'], 'Bearer access-token');
  expect(captured.headers['x-device-id'], 'management-phone');
  expect(captured.headers['x-session-id'], isNull);
  expect(overview.currency, 'PHP');
  expect(overview.generatedAt.isUtc, isTrue);
  expect(
    overview.metric(ManagementDashboardMetricKey.outstandingBalance)?.amount,
    '987654.32',
  );
});
```

Add table-driven failures for invalid/missing timestamp, non-PHP currency, non-list metrics, duplicate known key, negative or bool count, number-valued amount, negative amount, amount not fixed to two decimals, missing both count/amount, invalid date, and an invalid field combination. Assert `SpinaApiException.code == 'invalid_management_dashboard_overview'`.

Add an unknown-key case that succeeds, renders no metric for the key, and stores that server key in `ignoredMetricKeys`.

- [ ] **Step 2: Run the Flutter repository test and verify the red state**

Run from `gilbic_mobile`:

```powershell
flutter test test/management_dashboard_overview_repository_test.dart
```

Expected: compilation fails because the overview model/repository do not exist.

- [ ] **Step 3: Implement the closed metric-key model**

Define the enum with exact server keys:

```dart
enum ManagementDashboardMetricKey {
  activeClients('portfolio.active_clients'),
  activeLoans('portfolio.active_loans'),
  overdueLoans('portfolio.overdue_loans'),
  outstandingBalance('portfolio.outstanding_balance'),
  latestCollections('collections.latest_day'),
  unremittedCollections('collections.unremitted'),
  assignedRemittances('queues.remittances_assigned'),
  protectedRenewals('queues.renewals_protected'),
  staffRegistrations('queues.staff_registrations'),
  clientRegistrations('queues.client_registrations'),
  collectorMobileDevices('queues.collector_mobile_devices'),
  borrowerSupport('queues.borrower_support'),
  unreadActivity('activity.unread');

  const ManagementDashboardMetricKey(this.serverKey);
  final String serverKey;
}
```

Define:

```dart
class ManagementDashboardMetric {
  const ManagementDashboardMetric({
    required this.key,
    this.count,
    this.amount,
    this.asOfDate,
  });

  final ManagementDashboardMetricKey key;
  final int? count;
  final String? amount;
  final DateTime? asOfDate;
}

class ManagementDashboardOverview {
  const ManagementDashboardOverview({
    required this.generatedAt,
    required this.currency,
    required this.metrics,
    required this.ignoredMetricKeys,
  });

  final DateTime generatedAt;
  final String currency;
  final List<ManagementDashboardMetric> metrics;
  final List<String> ignoredMetricKeys;

  ManagementDashboardMetric? metric(ManagementDashboardMetricKey key) {
    for (final metric in metrics) {
      if (metric.key == key) return metric;
    }
    return null;
  }
}
```

Use `RegExp(r'^(0|[1-9]\d*)\.\d{2}$')` for money. Require UTC/offset-bearing timestamps and calendar dates that round-trip to the same `yyyy-MM-dd` string. Permit `as_of_date` only for `latestCollections`. Require exact expected fields per known key: count-only, amount-only, or combined count+amount as defined by the spec.

The exact shape table is: `activeClients`, `activeLoans`, `overdueLoans`,
`protectedRenewals`, `staffRegistrations`, `clientRegistrations`,
`collectorMobileDevices`, `borrowerSupport`, and `unreadActivity` are
count-only; `outstandingBalance` is amount-only; `latestCollections` is
count+amount with optional date; `unremittedCollections` and
`assignedRemittances` are count+amount without a date. Reject any extra
count/amount/date combination on a known key.

- [ ] **Step 4: Implement the authenticated HTTP repository**

Use this exact interface:

```dart
abstract interface class ManagementDashboardOverviewRepository {
  Future<ManagementDashboardOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  });
}
```

The implementation calls only `/api/mobile/v1/management/dashboard-overview` with `Accept`, `Authorization`, and `X-Device-Id`. It must not send `X-Session-Id`. Convert transport failures to `network_unavailable`, unreadable JSON to `invalid_server_response`, malformed 2xx data to `invalid_management_dashboard_overview`, and preserve safe FastAPI `detail.message`/`detail.code` on non-2xx responses.

- [ ] **Step 5: Run and format the Flutter repository slice**

Run:

```powershell
dart format lib/src/core/management/management_dashboard_overview.dart lib/src/core/management/management_dashboard_overview_repository.dart test/management_dashboard_overview_repository_test.dart
flutter test test/management_dashboard_overview_repository_test.dart
```

Expected: formatting succeeds and all repository/parser tests pass.

- [ ] **Step 6: Commit the Flutter contract slice**

```powershell
git add -- gilbic_mobile/lib/src/core/management/management_dashboard_overview.dart gilbic_mobile/lib/src/core/management/management_dashboard_overview_repository.dart gilbic_mobile/test/management_dashboard_overview_repository_test.dart
git diff --cached --check
git commit -m "feat: add management overview client"
```

### Task 4: Live Management dashboard state, cards, and navigation

**Files:**
- Modify: `gilbic_mobile/lib/src/features/management/management_dashboard.dart`
- Modify: `gilbic_mobile/lib/src/features/dashboard/role_dashboard.dart`
- Modify: `gilbic_mobile/lib/src/features/dashboard/enhanced_role_dashboard.dart`
- Create: `gilbic_mobile/test/management_dashboard_live_overview_test.dart`
- Modify: `gilbic_mobile/test/management_dashboard_information_architecture_test.dart`

**Interfaces:**
- Consumes: `ManagementDashboardOverviewRepository` and model types from Task 3, existing `DeviceIdentityProvider.load()`, `_ManagementAction`, `_ManagementModule.isAvailableFor`, and existing protected destination widgets.
- Produces: optional repository injection through dashboard composition and a stateful `ManagementDashboard` with live overview region.

- [ ] **Step 1: Write failing loading, success, omission, and error widget tests**

Use a controllable fake:

```dart
class FakeManagementDashboardOverviewRepository
    implements ManagementDashboardOverviewRepository {
  FakeManagementDashboardOverviewRepository(this.responses);

  final Queue<Future<ManagementDashboardOverview>> responses;
  int calls = 0;

  @override
  Future<ManagementDashboardOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) {
    calls += 1;
    expect(deviceId, 'management-phone');
    return responses.removeFirst();
  }
}
```

Prove these keyed states:

- `management-overview-loading` while the first future is unresolved;
- `management-overview-facts` with active clients/loans, overdue, outstanding, latest collections, and unremitted;
- `management-overview-attention` with only nonzero authorized queues/activity;
- `management-overview-no-pending` when every returned attention metric is zero;
- no text/card for omitted specialized keys;
- `management-overview-error` and `management-overview-retry` after initial failure while `management-section-review` and all other permitted launcher sections remain present.

- [ ] **Step 2: Run the live overview widget test and verify the red state**

Run from `gilbic_mobile`:

```powershell
flutter test test/management_dashboard_live_overview_test.dart
```

Expected: compilation fails because injection and overview widgets do not exist.

- [ ] **Step 3: Convert ManagementDashboard to stateful loading with generation protection**

Add the optional injectable field without breaking production callers:

```dart
class ManagementDashboard extends StatefulWidget {
  const ManagementDashboard({
    required this.session,
    required this.onSignOut,
    required this.paymentSubmissionRepository,
    required this.deviceIdentityProvider,
    required this.collectionDeviceSequence,
    this.overviewRepository,
    super.key,
  });

  final ManagementDashboardOverviewRepository? overviewRepository;
}
```

State initializes `_repository = widget.overviewRepository ?? SpinaManagementDashboardOverviewRepository()`, declares nullable `_overview`, `_overviewError`, `_overviewStatusCode`, and `_deviceId` fields plus integer `_requestGeneration`, loads the installation identity once, and uses:

```dart
Future<void> _loadOverview({bool refresh = false}) async {
  final generation = ++_requestGeneration;
  setState(() {
    _loadingOverview = true;
    _overviewError = null;
    _overviewStatusCode = null;
  });
  try {
    final deviceId = _deviceId ??
        (await widget.deviceIdentityProvider.load()).installationId;
    _deviceId = deviceId;
    final overview = await _repository.loadOverview(
      widget.session,
      deviceId: deviceId,
    );
    if (!mounted || generation != _requestGeneration) return;
    setState(() => _overview = overview);
  } on Object catch (error) {
    if (!mounted || generation != _requestGeneration) return;
    setState(() {
      _overviewError = error is SpinaApiException
          ? error.message
          : 'The live Management overview could not be loaded.';
      _overviewStatusCode = error is SpinaApiException
          ? error.statusCode
          : null;
    });
  } finally {
    if (mounted && generation == _requestGeneration) {
      setState(() => _loadingOverview = false);
    }
  }
}
```

Increment `_requestGeneration` in `dispose`. Keep the last successful overview during a refresh failure and preserve its original `generatedAt`.

The initial error panel distinguishes HTTP 401 (`Session expired`, with a
`Sign in again` action that calls `onSignOut`), HTTP 403 (`Live data access
unavailable`, with retry and the existing launchers still present), and
network/server failures (`Live overview unavailable`, with retry). Do not
automatically sign out on every 403 because permission loss and revoked-device
responses share that status at current boundaries.

- [ ] **Step 4: Add platform-safe presentation and exact metric mapping**

Insert `_ManagementLiveOverview` after `_ManagementWelcomeCard` and before the six existing sections. Use compact wrapping cards, not a fixed column/grid that can overflow at 360 pixels.

Map keys exactly:

```dart
const _metricActions = <ManagementDashboardMetricKey, _ManagementAction>{
  ManagementDashboardMetricKey.activeClients: _ManagementAction.loans,
  ManagementDashboardMetricKey.activeLoans: _ManagementAction.loans,
  ManagementDashboardMetricKey.overdueLoans: _ManagementAction.loans,
  ManagementDashboardMetricKey.outstandingBalance: _ManagementAction.loans,
  ManagementDashboardMetricKey.latestCollections:
      _ManagementAction.loanOperations,
  ManagementDashboardMetricKey.unremittedCollections:
      _ManagementAction.loanOperations,
  ManagementDashboardMetricKey.assignedRemittances:
      _ManagementAction.remittanceNotifications,
  ManagementDashboardMetricKey.protectedRenewals:
      _ManagementAction.renewals,
  ManagementDashboardMetricKey.staffRegistrations:
      _ManagementAction.staffDevices,
  ManagementDashboardMetricKey.clientRegistrations:
      _ManagementAction.clientRegistrationApprovals,
  ManagementDashboardMetricKey.collectorMobileDevices:
      _ManagementAction.staffDevices,
  ManagementDashboardMetricKey.borrowerSupport:
      _ManagementAction.support,
  ManagementDashboardMetricKey.unreadActivity:
      _ManagementAction.alertsActivity,
};
```

Resolve the corresponding existing `_ManagementModule` by action and call the same `_openModule` method so tap-time permissions remain identical. Label overdue as `Overdue loans`, unremitted as `Unremitted collector cash`, and show `Updated <localized server time>`. Format the validated decimal string with a pure display helper that inserts thousands separators without parsing to `double`.

- [ ] **Step 5: Propagate optional repository injection**

Add nullable `managementDashboardOverviewRepository` to `EnhancedRoleDashboard` and `RoleDashboard`, pass it unchanged, and provide it as `overviewRepository` only when constructing `ManagementDashboard`. Production composition omits it and therefore uses the real HTTP repository.

- [ ] **Step 6: Add refresh, stale-response, navigation, and accessibility tests**

Extend the widget test to prove:

```dart
testWidgets('late initial response cannot replace a newer refresh', (tester) async {
  final first = Completer<ManagementDashboardOverview>();
  final second = Completer<ManagementDashboardOverview>();
  final repository = FakeManagementDashboardOverviewRepository(
    Queue.of(<Future<ManagementDashboardOverview>>[
      first.future,
      second.future,
    ]),
  );
  await pumpDashboard(tester, repository: repository);

  await tester.tap(find.byKey(const Key('management-overview-refresh')));
  await tester.pump();
  second.complete(_newerOverview);
  await tester.pumpAndSettle();
  first.complete(_olderOverview);
  await tester.pumpAndSettle();

  expect(find.text('222 active clients'), findsOneWidget);
  expect(find.text('111 active clients'), findsNothing);
});
```

Also prove retry, pull-to-refresh, failed-refresh-with-old-timestamp, HTTP 401
sign-in action, HTTP 403 access warning without automatic sign-out, every metric
destination, tap-time permission denial, and 360x640 at 1.3x text. Modify
`management_dashboard_information_architecture_test.dart` to inject a completed
baseline fake so it makes no network request and still proves all six groups and
21 launchers.

- [ ] **Step 7: Run focused Flutter tests and analyzer**

Run:

```powershell
dart format lib/src/features/management/management_dashboard.dart lib/src/features/dashboard/role_dashboard.dart lib/src/features/dashboard/enhanced_role_dashboard.dart test/management_dashboard_live_overview_test.dart test/management_dashboard_information_architecture_test.dart
flutter test test/management_dashboard_overview_repository_test.dart test/management_dashboard_live_overview_test.dart test/management_dashboard_information_architecture_test.dart test/management_staff_devices_page_test.dart test/management_staff_detail_page_test.dart
flutter analyze --fatal-infos
```

Expected: all focused tests and analyzer pass with no overflow, unawaited-future, or context-after-await issue.

- [ ] **Step 8: Commit the dashboard slice**

```powershell
git add -- gilbic_mobile/lib/src/features/management/management_dashboard.dart gilbic_mobile/lib/src/features/dashboard/role_dashboard.dart gilbic_mobile/lib/src/features/dashboard/enhanced_role_dashboard.dart gilbic_mobile/test/management_dashboard_live_overview_test.dart gilbic_mobile/test/management_dashboard_information_architecture_test.dart
git diff --cached --check
git commit -m "feat: show live management priorities"
```

### Task 5: Authoritative cross-platform documentation and full verification

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/system-map.md`
- Modify: `docs/architecture/progress-map.md`

**Interfaces:**
- Consumes: the approved design, actual implemented API/Flutter behavior, and frozen Issue #296 tracking rules.
- Produces: one current-vs-intended platform statement that future chats can retrieve without treating legacy Desktop/UI state as authority.

- [ ] **Step 1: Update the authoritative repository documentation**

Make these exact documentation changes:

- In `README.md`, expand Gilbic Mobile responsibility to Management/Employee capability parity delivered through the same FastAPI/permission model, while marking the live overview as implemented only after tests pass.
- In `system-map.md`, replace `Office Staff / Encoder` with canonical `Employee`, show both Management and Employee connected to Desktop and mobile, and add a `Current vs intended` table. Current must say Desktop has mature legacy/local workflows and Mobile has incremental protected modules; intended must say equivalent Management/Employee capabilities share backend contracts and official outcomes.
- In the ownership table, state that role/permission and financial authority are server-derived; neither Flutter nor legacy Desktop role labels are authoritative.
- In `progress-map.md`, retain the archive but add a dated supersession notice that the old “native mobile expansion deferred to V1.1+” statement is historical and replaced by the approved cross-platform parity direction. Do not turn the archived file back into a live tracker.
- Document that New Client Fund, renewal fund, and smart client capacity remain intended future server-authoritative modules, not values calculated by this overview.

- [ ] **Step 2: Run documentation and changed-file checks**

Run:

```powershell
rg -n "functional capability parity|Current vs intended|New Client Fund|historical" README.md docs/architecture/system-map.md docs/architecture/progress-map.md
git diff --check
python -m compileall -q gilbic_backend/src/gilbic_backend
```

Expected: all required statements are present, no whitespace errors exist, and Python compilation succeeds.

- [ ] **Step 3: Run the complete backend and Flutter suites**

Run:

```powershell
python -m pytest -q gilbic_backend/tests spina_backend_mobile/tests
ruff check gilbic_backend/src gilbic_backend/tests spina_backend_mobile/src spina_backend_mobile/tests
ruff format --check gilbic_backend/src gilbic_backend/tests spina_backend_mobile/src spina_backend_mobile/tests
pyright gilbic_backend/src/gilbic_backend spina_backend_mobile/src/spina_mobile_collections
```

Then from `gilbic_mobile`:

```powershell
flutter test
flutter analyze --fatal-infos
```

Expected: all required checks pass. Record any environment-only PostgreSQL skip separately; do not call the feature exact-head green while a required disposable-PostgreSQL run is missing.

- [ ] **Step 4: Review the exact diff for security and scope**

Run:

```powershell
git status --short --branch
git diff --stat codex/ca2-staff-device-admin...HEAD
git diff codex/ca2-staff-device-admin...HEAD -- gilbic_backend/src/gilbic_backend/management_dashboard_overview_repository.py gilbic_backend/src/gilbic_backend/management_dashboard_overview_api.py gilbic_mobile/lib/src/core/management/management_dashboard_overview.dart gilbic_mobile/lib/src/features/management/management_dashboard.dart
```

Confirm manually from the diff: one SQL execute, actor scoping, specialized omission, no PII, no float money, no migration, no local financial calculation, existing launchers intact, no unrelated user files, and no production/live operation.

- [ ] **Step 5: Commit authoritative documentation**

```powershell
git add -- README.md docs/architecture/system-map.md docs/architecture/progress-map.md
git diff --cached --check
git commit -m "docs: align desktop and mobile capabilities"
```

### Task 6: Independent review, exact-head evidence, Draft PR, and status sync

**Files:**
- No new implementation files unless review identifies a verified defect.
- Artifact output: `artifacts/SPINA-CA2-<exact-head>-arm64-x64-debug.apk` outside the commit.

**Interfaces:**
- Consumes: all commits from Tasks 1–5.
- Produces: review evidence, exact-head CI state, Android review artifact/hash, Draft PR, and matching GitHub/Notion/Create State checkpoint without claiming completion prematurely.

- [ ] **Step 1: Obtain independent specification and standards/code review**

Reviewers compare the exact branch diff to:

```text
docs/superpowers/specs/2026-08-29-ca2-management-live-overview-design.md
docs/superpowers/plans/2026-08-29-ca2-management-live-overview.md
```

Require explicit findings for authorization, permission omission, actor scoping, one-statement coherence, metric semantics, money parsing, stale response handling, navigation, accessibility, and scope. Resolve every Critical or Important finding test-first; repeat the focused and affected full checks after each fix.

- [ ] **Step 2: Build and verify the exact-head Android review artifact**

From `gilbic_mobile`:

```powershell
flutter build apk --debug --target-platform android-arm64,android-x64
```

Copy the build output to the exact-head artifact name, calculate `Get-FileHash -Algorithm SHA256`, record byte size, install to the approved emulator, cold-launch, and check logs for fatal exceptions. Do not call this unsigned/debug artifact production-ready.

- [ ] **Step 3: Push and open the stacked Draft pull request**

```powershell
git status --short --branch
git push -u origin codex/ca2-management-live-overview
gh pr create --draft --base codex/ca2-staff-device-admin --head codex/ca2-management-live-overview --title "CA2: add live Management overview" --body "Adds one server-authoritative, permission-filtered Management dashboard snapshot and a resilient Flutter overview mapped to existing protected workflows. Includes cross-platform Management/Employee capability-parity documentation. No migration, merge, deploy, protected restart, live database action, production signing, or store release is included."
```

Expected: the PR is Draft, stacked on PR #376's branch, and contains only the approved design, plan, backend, Flutter, tests, and authoritative documentation.

- [ ] **Step 4: Wait for all permanent CI lanes on the exact pushed SHA**

Run:

```powershell
gh pr checks --watch
git rev-parse HEAD
```

Record the exact SHA and all five permanent CI conclusions. If a check fails, diagnose and fix on the same branch, rerun locally, push the new SHA, and restart the exact-head evidence check.

- [ ] **Step 5: Sync GitHub Issue #296 and project memory without overclaiming**

Add a GitHub Issue #296 comment containing branch, Draft PR URL, exact base/head SHAs, implemented metric keys, permission-omission rule, test totals, PostgreSQL execution/skip, reviewer result, CI links/conclusions, APK name/size/SHA-256, and remaining authenticated Android/iOS gates. Do not check CA2 or CB1 complete from automated evidence alone.

Update Notion `SPINA Project Memory` and Create State with the same facts plus:

```text
Current: live Management overview implemented on a stacked Draft branch.
Intended: Desktop and mobile reach functional Management/Employee capability parity through the same FastAPI contracts and server permissions.
Deferred: New Client Fund, renewal fund, smart client capacity, full accounting/HR/CRM parity, iOS acceptance, merge, deployment, and live migration.
```

If a connector is unavailable, record the exact unsynced destination as an open release-evidence item; do not invent a successful update.

- [ ] **Step 6: Final clean-state and restriction check**

```powershell
git status --short --branch
git log --oneline codex/ca2-staff-device-admin..HEAD
gh pr view --json isDraft,baseRefName,headRefName,url,statusCheckRollup
```

Expected: clean feature worktree, Draft PR with correct stack, exact-head checks visible, artifacts uncommitted, and no merge/deploy/restart/live-database action performed.
