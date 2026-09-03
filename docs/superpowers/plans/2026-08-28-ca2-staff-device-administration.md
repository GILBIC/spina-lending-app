# CA2 Protected Staff Device Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved CA2 staff-account and device-administration slice as two stacked Draft PRs: a protected FastAPI/PostgreSQL contract followed by a permission-aware Flutter management experience.

**Architecture:** The backend remains the authority for staff search, account mutations, device approval, replacement, and audit. Collector mobile login creates or reuses a committed pending device record and returns a stable denial without tokens. The Flutter client stays online-only, sends the current bearer token and installation identity on every request, renders only permission-appropriate controls, and reloads authoritative state after every mutation.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, psycopg 3, PostgreSQL, pytest, Flutter 3.44.7, Dart, `http`, `flutter_test`, GitHub Actions, GitHub CLI.

**Spec:** `docs/superpowers/specs/2026-08-28-ca2-staff-device-administration-design.md`

## Global Constraints

- Start backend work on `codex/ca2-device-approval-api` at `e1c252899f0a7f5f1b8dfc65d31fa2c857e86183`; target `codex/ca2-management-command-center` with a Draft PR.
- Start mobile work from the final backend head on `codex/ca2-staff-device-admin`; target `codex/ca2-device-approval-api` with a Draft PR.
- Do not merge, deploy, restart the protected backend, run a protected/live migration, or touch a protected/live database.
- Use only `GILBIC_TEST_DATABASE_URL` for real PostgreSQL tests. A missing disposable database URL is a documented skip, not permission to substitute a live URL.
- Preserve the unrelated working-tree changes in `gilbic_backend/src/gilbic_backend/cross_remittance_repository.py` and `gilbic_backend/tests/test_cross_remittance_api.py`; never stage them.
- Do not add a migration. `core.devices.status` already supports `pending`.
- Never expose `auth_user_id`, `device_identifier_hash`, bearer tokens, refresh tokens, or raw identity-provider values in management payloads, UI, logs, audit details, screenshots, or PR text.
- Keep directory authorization broad enough for `account.manage` or `device.manage`; keep every mutation protected by its exact single permission.
- Treat invitation, role/status changes, and device changes as online-only operations. Do not queue, optimistically confirm, or automatically retry a mutation whose result is uncertain.
- Use `apply_patch` for hand edits. Stage only named files. Run `git diff --check` before every commit.

---

### Task 1: Extend the staff-directory backend contract

**Files:**

- Modify: `gilbic_backend/tests/test_management_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/management_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/management_repository.py`

- [ ] Add failing API tests proving that `GET /api/v1/management/accounts` accepts `q`, `role`, `status`, `staff_only`, `limit`, and `offset`; allows a caller with only `device.manage`; rejects a caller with neither permission; forwards normalized filters to the repository; and omits `auth_user_id` from every response account.

Use this fake signature so production and test interfaces move together:

```python
def list_accounts(
    self,
    *,
    query: str | None = None,
    role_code: str | None = None,
    account_status: str | None = None,
    staff_only: bool = False,
    limit: int = 100,
    offset: int = 0,
):
    self.list_account_calls.append(
        {
            "query": query,
            "role_code": role_code,
            "account_status": account_status,
            "staff_only": staff_only,
            "limit": limit,
            "offset": offset,
        }
    )
    return list(self.accounts)
```

The response assertion must be explicit:

```python
response = client.get(
    "/api/v1/management/accounts",
    params={
        "q": "  Ana  ",
        "role": "collector",
        "status": "active",
        "staff_only": "true",
        "limit": 25,
        "offset": 50,
    },
    headers={"Authorization": "Bearer token", "X-Device-Id": "manager-phone"},
)
assert response.status_code == 200
assert response.json()["data"]["accounts"][0].get("auth_user_id") is None
assert management.list_account_calls == [{
    "query": "Ana",
    "role_code": "collector",
    "account_status": "active",
    "staff_only": True,
    "limit": 25,
    "offset": 50,
}]
```

- [ ] Run the new API tests and confirm they fail for the missing query parameters, any-permission authorization, and payload redaction.

Run: `python -m pytest -q gilbic_backend/tests/test_management_api.py -k "list_accounts or account_payload"`

Expected: failures show the current endpoint requires `account.manage`, the fake receives only paging, and the payload still contains `auth_user_id`.

- [ ] Implement a narrow any-permission actor helper and use it only on the account-directory read endpoint.

```python
def _management_actor_with_any_permission(
    *,
    authorization: str | None,
    device_identifier: str | None,
    permissions: tuple[str, ...],
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> AccountContext:
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=device_identifier,
        auth=auth,
        accounts=accounts,
    )
    if not any(permission in actor.permissions for permission in permissions):
        raise HTTPException(status_code=403, detail="This action is not permitted for your account.")
    return actor
```

Keep invite, role, and account-status routes on `account.manage`, and device list/status routes on `device.manage`.

- [ ] Add typed query parameters to the endpoint and remove `auth_user_id` from `_account_payload`.

```python
q: str | None = Query(default=None, max_length=200),
role_code: Literal["collector", "employee", "management"] | None = Query(
    default=None,
    alias="role",
),
account_status: Literal["active", "inactive", "locked", "pending"] | None = Query(
    default=None,
    alias="status",
),
staff_only: bool = Query(default=False),
```

Pass `(q or "").strip() or None` and every remaining filter to `management.list_accounts`.

- [ ] Extend `PostgresManagementRepository.list_accounts` with a parameterized SQL query that filters before grouping and paging.

Use this public signature:

```python
def list_accounts(
    self,
    *,
    query: str | None = None,
    role_code: str | None = None,
    account_status: str | None = None,
    staff_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[AccountAdminRecord]:
```

Build `where_clauses` and `parameters` without interpolating user input. Search `u.username`, `u.full_name`, and `coalesce(u.email, '')` with one escaped `%value%` parameter repeated three times. Use correlated `exists` clauses for role filters so aggregation is not truncated. For `staff_only`, require an `exists` role in `('collector', 'employee', 'management')`. End with:

```sql
group by u.id
order by u.created_at desc, u.username, u.id
limit %s offset %s
```

- [ ] Re-run the focused tests and confirm the directory contract passes.

Run: `python -m pytest -q gilbic_backend/tests/test_management_api.py -k "list_accounts or account_payload"`

Expected: all selected tests pass.

- [ ] Check the diff and commit only the three Task 1 files.

Run: `git diff --check`

Run: `git add gilbic_backend/tests/test_management_api.py gilbic_backend/src/gilbic_backend/management_api.py gilbic_backend/src/gilbic_backend/management_repository.py`

Run: `git commit -m "feat: add protected staff directory filters"`

---

### Task 2: Persist pending Collector mobile devices and return a stable denial

**Files:**

- Modify: `gilbic_backend/tests/test_auth_api.py`
- Create: `gilbic_backend/tests/test_account_device_approval_postgres.py`
- Modify: `gilbic_backend/src/gilbic_backend/account_repository.py`
- Modify: `gilbic_backend/src/gilbic_backend/auth_api.py`

- [ ] Add failing auth API tests for the stable error envelope and absence of tokens.

Add `DeviceApprovalRequired` behavior to the fake repository and assert this exact contract:

```python
assert response.status_code == 403
assert response.json() == {
    "success": False,
    "error": {
        "code": "device_approval_required",
        "message": "This Collector device is awaiting Management approval.",
    },
}
assert "access_token" not in response.text
assert "refresh_token" not in response.text
```

Also retain explicit tests that a revoked device still returns its existing denial and that Management, Employee, Client, web, and desktop behavior does not enter the Collector-mobile pending path.

- [ ] Add disposable-PostgreSQL tests for a Collector's first Android login, repeated login, existing pending login, approved login, and revoked login.

Mark the module with the repository's established `GILBIC_TEST_DATABASE_URL` skip pattern. Use unique UUIDs and usernames. Insert the test user, role, and device fixture directly, call `PostgresAccountRepository.activate_and_register_device`, then verify in a new connection that:

```python
assert pending_rows == [
    {
        "platform": "android",
        "status": "pending",
        "device_identifier_hash": PostgresAccountRepository.device_hash("collector-phone-b"),
    }
]
```

Delete each test user in `finally`; rely on foreign-key cascades only inside the disposable database.

- [ ] Run the focused tests and confirm failure before implementation.

Run: `python -m pytest -q gilbic_backend/tests/test_auth_api.py -k "device_approval or revoked"`

Run: `python -m pytest -q gilbic_backend/tests/test_account_device_approval_postgres.py`

Expected: API contract and pending persistence tests fail because unknown devices are currently activated.

- [ ] Add the stable exception next to the existing device exceptions.

```python
class DeviceApprovalRequired(AccountError):
    code = "device_approval_required"
```

- [ ] Change `activate_and_register_device` so unknown Collector Android/iOS devices are inserted as `pending`, committed, and denied only after leaving the transaction.

Use a local flag so the exception cannot roll back the insert:

```python
approval_required = False
with open_connection() as connection:
    with connection.transaction():
        # Lock the user, load roles, and validate account state first.
        # Collector mobile pending devices stay pending; other valid devices follow existing activation behavior.
        approval_required = is_collector and normalized_platform in {"android", "ios"} and (
            device is None or device[1] == "pending"
        )
        # Existing active devices continue; revoked devices still raise DeviceRevoked.
    if approval_required:
        raise DeviceApprovalRequired(
            "This Collector device is awaiting Management approval."
        )
```

Load `is_collector` in the existing locked user query with another role `exists`. For an existing pending Collector Android/iOS row, update only `platform`, `app_version`, and `last_seen_at`; do not change its status. For an unknown Collector Android/iOS device, insert with status `pending`. For a non-Collector role or non-mobile platform, preserve the current behavior of registering or updating the device as active. Keep the unique `(user_id, device_identifier_hash)` guarantee as the duplicate-row defense.

- [ ] Distinguish pending from revoked in `get_context_for_device`.

```python
if device[1] == "pending":
    raise DeviceApprovalRequired(
        "This Collector device is awaiting Management approval."
    )
if device[1] != "active":
    raise DeviceRevoked("This device has been revoked.")
```

- [ ] Return the stable login error envelope from `auth_api.login`.

```python
except DeviceApprovalRequired as exc:
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "error": {"code": exc.code, "message": str(exc)},
        },
    )
```

Import `JSONResponse` from `fastapi.responses` and `DeviceApprovalRequired` from the account repository. Do not include the already-created Supabase session in the response.

- [ ] Re-run both focused test groups.

Run: `python -m pytest -q gilbic_backend/tests/test_auth_api.py -k "device_approval or revoked"`

Run: `python -m pytest -q gilbic_backend/tests/test_account_device_approval_postgres.py`

Expected: all selected tests pass, or the PostgreSQL module reports its documented skip when no disposable URL is configured.

- [ ] Check and commit only the Task 2 files.

Run: `git diff --check`

Run: `git add gilbic_backend/tests/test_auth_api.py gilbic_backend/tests/test_account_device_approval_postgres.py gilbic_backend/src/gilbic_backend/account_repository.py gilbic_backend/src/gilbic_backend/auth_api.py`

Run: `git commit -m "feat: require approval for new collector devices"`

---

### Task 3: Make Collector device replacement transactional and auditable

**Files:**

- Modify: `gilbic_backend/tests/test_management_api.py`
- Create: `gilbic_backend/tests/test_management_device_administration_postgres.py`
- Modify: `gilbic_backend/src/gilbic_backend/management_repository.py`

- [ ] Add failing API fake tests covering `pending -> active`, `active -> revoked`, `revoked -> active`, no-op responses, and self-revocation protection. Verify the route still requires only `device.manage`.

The fake must record `(actor_user_id, device_id, device_status)` and return the selected device. The no-op API response remains successful because idempotence is decided in the repository.

- [ ] Add disposable-PostgreSQL tests for the transaction invariants.

Create fixtures with two active Collector mobile devices, one pending Collector mobile device, one Employee device, and a separate Management actor. Assert:

```python
assert active_collector_mobile_count == 1
assert selected_status == "active"
assert displaced_statuses == ["revoked", "revoked"]
assert selected_audit["details"] == {
    "user_id": str(collector_user_id),
    "platform": "android",
    "previous_status": "pending",
    "new_status": "active",
}
assert all("device_identifier_hash" not in audit["details"] for audit in audits)
```

Also assert each displaced device has one `device.replacement_auto_revoke` audit containing only `user_id`, `platform`, `previous_status`, and `new_status`.

- [ ] Add an audit-failure rollback test and a concurrency test.

For rollback, subclass the repository and override `_audit` to raise `RuntimeError("forced audit failure")`; after the call, verify the selected and displaced statuses are unchanged. For concurrency, use `ThreadPoolExecutor(max_workers=2)` and approve two pending Collector mobile devices for the same user at once. After both futures settle, query a fresh connection and assert the active Android/iOS count is at most one.

- [ ] Run the focused tests and confirm they fail before implementation.

Run: `python -m pytest -q gilbic_backend/tests/test_management_api.py -k "device"`

Run: `python -m pytest -q gilbic_backend/tests/test_management_device_administration_postgres.py`

Expected: replacement, no-op audit, rollback, and concurrency assertions fail against the current single-row update.

- [ ] Rework `set_device_status` to lock in a consistent order and audit previous/new states.

Use these transaction steps in order:

```python
with connection.cursor(row_factory=dict_row) as cursor:
    cursor.execute("select user_id from core.devices where id = %s", (device_id,))
    identity = cursor.fetchone()
if not identity:
    raise AccountNotFound("Registered device was not found.")
self._lock_user(connection, identity["user_id"])
with connection.cursor(row_factory=dict_row) as cursor:
    cursor.execute(DEVICE_SELECT_SQL + " where id = %s for update", (device_id,))
    selected = cursor.fetchone()
```

After the target-user lock, load whether the user has role `collector`. If the requested state equals the selected state, return the selected record without an update or audit. Keep self-device protection for a Management actor revoking a device owned by that same account.

When activating an Android/iOS device for a Collector, select all other active Android/iOS devices for that user with `for update`, update them to `revoked`, and write one audit per displaced device. Then update the selected device and write `device.status_change`. All updates and audits stay inside the same transaction.

Use these audit payloads:

```python
{
    "user_id": str(selected["user_id"]),
    "platform": selected["platform"],
    "previous_status": selected["status"],
    "new_status": normalized_status,
}
```

Do not place app version, device hashes, or external identity values in audit details. The audit row's existing actor, target, and timestamp fields plus the safe `user_id` and `platform` details preserve the approved operational evidence.

- [ ] Re-run the API and PostgreSQL tests.

Run: `python -m pytest -q gilbic_backend/tests/test_management_api.py -k "device"`

Run: `python -m pytest -q gilbic_backend/tests/test_management_device_administration_postgres.py`

Expected: all selected tests pass or the disposable-PostgreSQL module reports its documented skip.

- [ ] Check and commit only the Task 3 files.

Run: `git diff --check`

Run: `git add gilbic_backend/tests/test_management_api.py gilbic_backend/tests/test_management_device_administration_postgres.py gilbic_backend/src/gilbic_backend/management_repository.py`

Run: `git commit -m "feat: protect collector device replacement"`

---

### Task 4: Prove the backend contract and document the security flow

**Files:**

- Modify: `docs/architecture/system-map.md`
- Modify: `docs/architecture/debugging-playbook.md`
- Modify only when test adjustments are required by public signatures: `gilbic_backend/tests/test_management_api.py`

- [ ] Update the system map with the new login and approval sequence.

Record these exact states and authorities:

```text
Collector Android/iOS unknown device -> core.devices pending -> HTTP 403 device_approval_required -> no token response
Management device.manage approval -> target-user lock -> selected device active -> other active Collector phones revoked -> audit in one transaction
```

State that account-directory reads require either `account.manage` or `device.manage`, while mutations retain their exact permissions. State that no raw device identifier or hash crosses the administration API.

- [ ] Extend the debugging playbook's Supabase Auth/application-authorization table with separate diagnoses for pending approval and revoked devices. The pending row directs the operator to verify `core.devices.status = 'pending'`, the Collector role, Android/iOS platform, and the `device_approval_required` response without inspecting or sharing identifier hashes. Do not expand the playbook into a release summary.

- [ ] Run backend compilation and the complete backend/mobile-server test suites.

Run: `python -m compileall -q gilbic_backend/src spina_backend_mobile/src`

Run: `python -m pytest -q gilbic_backend/tests spina_backend_mobile/tests`

Expected: the complete suites pass; disposable PostgreSQL tests may skip only when `GILBIC_TEST_DATABASE_URL` is absent.

- [ ] When `GILBIC_TEST_DATABASE_URL` is available, re-run the two new PostgreSQL modules with skip reasons forbidden by inspection.

Run: `python -m pytest -q -rs gilbic_backend/tests/test_account_device_approval_postgres.py gilbic_backend/tests/test_management_device_administration_postgres.py`

Expected: both modules execute and pass. If they skip, record the missing disposable-database evidence in the Draft PR and do not claim the database invariant verified.

- [ ] Run a secret/identity diff scan.

Run: `git diff --check`

Run: `git diff --unified=0 | rg -n "auth_user_id|device_identifier_hash|access_token|refresh_token|SUPABASE|DATABASE_URL"`

Expected: matches are limited to internal repository logic, explicit negative tests, or documentation prohibitions; no mobile-facing payload, audit content, or credential value is present.

- [ ] Commit the architecture evidence files, plus only signature-driven test adjustments if needed.

Run: `git add docs/architecture/system-map.md`

Add `docs/architecture/debugging-playbook.md`. Add `gilbic_backend/tests/test_management_api.py` only when changed for a public-signature adjustment.

Run: `git commit -m "docs: describe protected device approval flow"`

---

### Task 5: Publish the backend Draft PR and cut the stacked mobile branch

**Files:**

- No source files expected.

- [ ] Confirm the backend branch contains only intended commits and the unrelated working files remain unstaged.

Run: `git status --short --branch`

Run: `git log --oneline codex/ca2-management-command-center..HEAD`

Run: `git diff --stat codex/ca2-management-command-center...HEAD`

Expected: only CA2 design/plan/backend commits are listed; the two unrelated files remain ordinary unstaged modifications.

- [ ] Push the backend branch without force.

Run: `git push -u origin codex/ca2-device-approval-api`

- [ ] Create a Draft PR targeting the management command-center branch.

Run:

```powershell
gh pr create --draft --base codex/ca2-management-command-center --head codex/ca2-device-approval-api --title "CA2: protect staff device administration API" --body "Implements the approved CA2 backend contract for staff-directory reads, pending Collector mobile devices, transactional single-active-device replacement, exact permissions, and audit evidence. No deployment, protected restart, protected migration, or live database action is included. Verification results and any disposable-PostgreSQL skips are recorded in the checks and PR updates."
```

- [ ] Capture the PR URL and initial checks.

Run: `gh pr view codex/ca2-device-approval-api --json number,url,isDraft,baseRefName,headRefName,statusCheckRollup`

Run: `gh pr checks codex/ca2-device-approval-api`

Expected: the PR is Draft, base is `codex/ca2-management-command-center`, and head is `codex/ca2-device-approval-api`.

- [ ] Create the mobile branch from the exact backend head.

Run: `git switch -c codex/ca2-staff-device-admin`

Run: `git merge-base --is-ancestor codex/ca2-device-approval-api HEAD`

Expected: the ancestry command exits zero.

---

### Task 6: Add the strict Flutter administration domain and HTTP repository

**Files:**

- Create: `gilbic_mobile/lib/src/core/management/management_administration.dart`
- Create: `gilbic_mobile/lib/src/core/management/management_administration_repository.dart`
- Modify: `gilbic_mobile/lib/src/core/config/api_config.dart`
- Create: `gilbic_mobile/test/management_administration_repository_test.dart`

- [ ] Write failing model and repository tests for all six calls: staff search, invite, role change, account-status change, device list, and device-status change.

Use `http/testing.dart` and assert every request contains:

```dart
expect(request.headers['authorization'], 'Bearer access-token');
expect(request.headers['x-device-id'], 'management-phone');
expect(request.headers['x-session-id'], isNull);
```

Assert the staff search URI contains `staff_only=true`, encoded `q`, `role`, `status`, `limit`, and `offset`. Assert invite bodies never contain `password` and reject the `client` role before network I/O. Assert malformed UUID, role, status, timestamp, or collection fields produce `SpinaApiException(code: 'invalid_server_response')`.

- [ ] Run the new test file and confirm it fails because the domain and repository do not exist.

Run: `flutter test test/management_administration_repository_test.dart`

Working directory: `gilbic_mobile`

- [ ] Implement validated immutable domain objects.

Use these public types and allowed values:

```dart
const managementStaffRoles = <String>{'collector', 'employee', 'management'};
const managementAccountStatuses = <String>{'active', 'inactive', 'locked', 'pending'};
const managementDeviceStatuses = <String>{'pending', 'active', 'revoked'};

final class ManagementStaffAccount {
  const ManagementStaffAccount({
    required this.id,
    required this.username,
    required this.email,
    required this.fullName,
    required this.status,
    required this.roles,
    required this.deviceCount,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String username;
  final String? email;
  final String fullName;
  final String status;
  final List<String> roles;
  final int deviceCount;
  final DateTime createdAt;
  final DateTime updatedAt;
}

final class ManagementDevice {
  const ManagementDevice({
    required this.id,
    required this.platform,
    required this.appVersion,
    required this.status,
    required this.registeredAt,
    required this.lastSeenAt,
  });

  final String id;
  final String platform;
  final String? appVersion;
  final String status;
  final DateTime registeredAt;
  final DateTime? lastSeenAt;
}

final class ManagementStaffPage {
  const ManagementStaffPage({
    required this.items,
    required this.nextOffset,
    required this.hasMore,
  });

  final List<ManagementStaffAccount> items;
  final int nextOffset;
  final bool hasMore;
}
```

Factories must throw `FormatException` for malformed required data. UUID validation uses `RegExp(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$')`. Do not model or retain `auth_user_id` or `user_id` on a device.

- [ ] Add exact API endpoint builders.

```dart
static Uri managementStaffAccountsEndpoint({
  String? query,
  String? role,
  String? status,
  int limit = 50,
  int offset = 0,
}) => endpoint('/api/v1/management/accounts').replace(
  queryParameters: <String, String>{
    'staff_only': 'true',
    'limit': '$limit',
    'offset': '$offset',
    if (query != null && query.trim().isNotEmpty) 'q': query.trim(),
    if (role != null) 'role': role,
    if (status != null) 'status': status,
  },
);
```

Add invite, role, account-status, device-list, and device-status endpoint builders using `Uri.encodeComponent` for path identifiers.

- [ ] Implement the repository interface and HTTP client.

```dart
abstract interface class ManagementAdministrationRepository {
  Future<ManagementStaffPage> loadStaff(
    UserSession session, {
    required String deviceId,
    String? query,
    String? role,
    String? status,
    int limit = 50,
    int offset = 0,
  });

  Future<ManagementStaffAccount> inviteStaff(
    UserSession session, {
    required String deviceId,
    required String username,
    required String email,
    required String fullName,
    required String role,
  });

  Future<ManagementStaffAccount> setRole(UserSession session, {required String deviceId, required String userId, required String role});
  Future<ManagementStaffAccount> setAccountStatus(UserSession session, {required String deviceId, required String userId, required String status});
  Future<List<ManagementDevice>> loadDevices(UserSession session, {required String deviceId, required String userId});
  Future<ManagementDevice> setDeviceStatus(UserSession session, {required String deviceId, required String userId, required String managedDeviceId, required String status});
}
```

Use one private `_request` matching the existing client-registration repository's error handling, but omit `X-Session-Id`. Translate network failures to `network_unavailable` and parse failures to `invalid_server_response`. Return `hasMore = items.length == limit` and `nextOffset = offset + items.length`.

- [ ] Re-run repository tests and analyzer on the new files.

Run: `dart format lib/src/core/management/management_administration.dart lib/src/core/management/management_administration_repository.dart lib/src/core/config/api_config.dart test/management_administration_repository_test.dart`

Run: `flutter test test/management_administration_repository_test.dart`

Run: `flutter analyze --fatal-infos`

Expected: repository tests and analysis pass.

- [ ] Check and commit only the Task 6 files.

Run: `git diff --check`

Run: `git add gilbic_mobile/lib/src/core/management/management_administration.dart gilbic_mobile/lib/src/core/management/management_administration_repository.dart gilbic_mobile/lib/src/core/config/api_config.dart gilbic_mobile/test/management_administration_repository_test.dart`

Run: `git commit -m "feat: add staff administration client"`

---

### Task 7: Surface pending-device login without persisting a session

**Files:**

- Modify: `gilbic_mobile/lib/src/core/auth/auth_repository.dart`
- Modify: `gilbic_mobile/test/auth_repository_test.dart`
- Modify: `gilbic_mobile/test/mobile_auth_error_parity_test.dart`
- Modify only if its existing error text is insufficient: `gilbic_mobile/lib/src/features/auth/login_page.dart`
- Modify only with the previous file: `gilbic_mobile/test/login_page_test.dart`

- [ ] Add a failing auth repository test for a `403` response with `error.code = device_approval_required`.

```dart
expect(
  repository.signIn(username: 'collector', password: 'password123'),
  throwsA(
    isA<SpinaApiException>()
      .having((error) => error.statusCode, 'statusCode', 403)
      .having((error) => error.code, 'code', 'device_approval_required')
      .having(
        (error) => error.message,
        'message',
        'This Collector device is awaiting Management approval.',
      ),
  ),
);
```

The repository test proves no `UserSession` is returned. Add an Android/iOS parity widget case around `GilbicApp` with `MemorySessionStore`, make the fake repository throw this error from `signIn`, submit the login form, then assert the approval message is visible and `await store.read()` is null.

- [ ] Run the focused test and confirm the code assertion fails.

Run: `flutter test test/auth_repository_test.dart --plain-name "pending Collector device requires Management approval"`

- [ ] Preserve the error code in `_sessionFromResponse`.

```dart
final error = stringMap(payload['error']);
throw SpinaApiException(
  response.statusCode == 401
      ? authenticationFailureMessage
      : apiErrorMessage(payload, statusCode: response.statusCode),
  statusCode: response.statusCode,
  code: firstNonEmptyString(<Object?>[error['code'], payload['code']]),
);
```

Do not construct `UserSession` or invoke persistence on this path.

- [ ] Inspect the login page's existing exception rendering. If it already shows `SpinaApiException.message`, leave it unchanged. If it replaces 403 messages, change it to show this specific code as: `This phone is waiting for Management approval. Ask Management to approve it, then sign in again.` Add the matching widget test.

- [ ] Re-run the auth tests and any changed login widget test.

Run: `flutter test test/auth_repository_test.dart test/mobile_auth_error_parity_test.dart`

If changed, run: `flutter test test/login_page_test.dart`

- [ ] Format, check, and commit only changed Task 7 files.

Run: `dart format lib/src/core/auth/auth_repository.dart test/auth_repository_test.dart test/mobile_auth_error_parity_test.dart`

Run: `git diff --check`

Run: `git add gilbic_mobile/lib/src/core/auth/auth_repository.dart gilbic_mobile/test/auth_repository_test.dart gilbic_mobile/test/mobile_auth_error_parity_test.dart`

Conditionally add the login page and its test only when changed.

Run: `git commit -m "fix: explain pending device approval at login"`

---

### Task 8: Add the any-permission dashboard launcher and resilient staff directory

**Files:**

- Modify: `gilbic_mobile/lib/src/features/management/management_dashboard.dart`
- Create: `gilbic_mobile/lib/src/features/management/management_staff_devices_page.dart`
- Create: `gilbic_mobile/test/management_staff_devices_page_test.dart`
- Modify: `gilbic_mobile/test/management_dashboard_information_architecture_test.dart`
- Modify: `gilbic_mobile/test/role_dashboard_permission_navigation_test.dart`

- [ ] Add failing dashboard tests proving the six-section layout remains intact, `Renewals & support` becomes `People, access & requests`, and `Staff & devices` is the first launcher in that section for either `account.manage` or `device.manage`. Assert the launcher opens exactly `ManagementStaffDevicesPage`, is absent without both permissions, and a direct tap-time check refuses navigation if `isAvailableFor` is false.

Add a permission-mode to `_ManagementModule`:

```dart
enum _PermissionMode { all, any }

bool isAvailableFor(UserSession session) => switch (permissionMode) {
  _PermissionMode.all => requiredPermissions.every(session.hasPermission),
  _PermissionMode.any => requiredPermissions.any(session.hasPermission),
};
```

All existing modules keep `_PermissionMode.all`. Only `Staff & devices` uses `any` with `['account.manage', 'device.manage']`.

- [ ] Add failing directory widget tests with a fake repository and fake device identity.

Cover initial loading, success, top-level error/retry, HTTP 403 permission-denied with refresh/back actions, unfiltered empty, filtered empty, pull refresh, role/status filters, server search after a 350 ms debounce, load more, UUID deduplication, and stale-response suppression. Also pump at `Size(360, 640)` with `MediaQuery.textScalerOf` equivalent `TextScaler.linear(1.3)` and assert no overflow exception.

Use deterministic requests in the fake:

```dart
expect(repository.loadCalls.last.query, 'ana');
expect(repository.loadCalls.last.role, 'collector');
expect(repository.loadCalls.last.status, 'active');
expect(repository.loadCalls.last.offset, 0);
expect(repository.loadCalls.last.deviceId, 'management-phone');
```

- [ ] Run the focused dashboard and directory tests and confirm they fail before implementation.

Run: `flutter test test/management_dashboard_information_architecture_test.dart test/role_dashboard_permission_navigation_test.dart test/management_staff_devices_page_test.dart`

- [ ] Add `_ManagementAction.staffDevices`, an exhaustive switch arm, and the launcher.

```dart
_ManagementAction.staffDevices => ManagementStaffDevicesPage(
  session: session,
  deviceIdentityProvider: deviceIdentityProvider,
),
```

The launcher title is `Staff & devices`, its icon is `Icons.manage_accounts_outlined`, and it is the first module under `People, access & requests`.

- [ ] Implement the directory state machine.

`ManagementStaffDevicesPage` accepts optional repository injection for tests and otherwise constructs `SpinaManagementAdministrationRepository`. Load the installation identity once in `initState`. Use an incrementing `_requestGeneration`; capture its value before each async load and ignore a response when the captured value differs from the current generation. On a new search/filter/refresh, clear paging state and request offset zero. On load-more, append only accounts whose UUID is not already present.

Render these distinct states with stable keys:

```dart
const Key('management-staff-loading')
const Key('management-staff-error')
const Key('management-staff-empty')
const Key('management-staff-filtered-empty')
const Key('management-staff-list')
const Key('management-staff-load-more')
```

Do not render account UUIDs or identity-provider values. Render full name, username, role label, account status, and device count.

- [ ] Re-run tests, format, and analyze.

Run: `dart format lib/src/features/management/management_dashboard.dart lib/src/features/management/management_staff_devices_page.dart test/management_staff_devices_page_test.dart test/management_dashboard_information_architecture_test.dart test/role_dashboard_permission_navigation_test.dart`

Run: `flutter test test/management_dashboard_information_architecture_test.dart test/role_dashboard_permission_navigation_test.dart test/management_staff_devices_page_test.dart`

Run: `flutter analyze --fatal-infos`

Expected: all focused tests and analysis pass.

- [ ] Check and commit only the Task 8 files.

Run: `git diff --check`

Run: `git add gilbic_mobile/lib/src/features/management/management_dashboard.dart gilbic_mobile/lib/src/features/management/management_staff_devices_page.dart gilbic_mobile/test/management_staff_devices_page_test.dart gilbic_mobile/test/management_dashboard_information_architecture_test.dart gilbic_mobile/test/role_dashboard_permission_navigation_test.dart`

Run: `git commit -m "feat: add staff and devices directory"`

---

### Task 9: Add protected staff detail, invitation, and confirmations

**Files:**

- Create: `gilbic_mobile/lib/src/features/management/management_staff_detail_page.dart`
- Create: `gilbic_mobile/lib/src/features/management/management_staff_invite_page.dart`
- Modify: `gilbic_mobile/lib/src/features/management/management_staff_devices_page.dart`
- Create: `gilbic_mobile/test/management_staff_detail_page_test.dart`
- Create: `gilbic_mobile/test/management_staff_invite_page_test.dart`
- Modify: `gilbic_mobile/test/management_staff_devices_page_test.dart`

- [ ] Add failing detail tests for permission partitioning and safe rendering.

Cover these matrices:

```text
account.manage only -> role/status controls visible; device section absent
device.manage only  -> device section/actions visible; role/status controls absent
both permissions    -> both control groups visible
neither permission  -> page shows permission state and no mutation controls
own account         -> destructive self account/device actions disabled
```

Assert UUIDs, `auth_user_id`, raw `user_id`, and device hashes never appear in rendered text. Assert a mutation success is shown only after the repository completes and a fresh authoritative account/device load succeeds.

- [ ] Add failing confirmation tests.

Every confirmation must include the person's name, current state, requested state, and consequence. Collector device approval must include: `Approving this phone revokes any other active Collector phone.` A network exception must retain the prior authoritative state and expose retry/refresh, with no automatic second mutation call. HTTP 403 shows that current server permissions no longer allow the action and offers refresh/back; HTTP 404 says the record is no longer available and refreshes the directory; HTTP 409 preserves the server conflict explanation and reloads current state before enabling another explicit decision.

- [ ] Add failing invitation tests.

The form requires full name, username, email, and one of Collector/Employee/Management. It never displays a password field or Client role. On a timeout or other uncertain result, show `Refresh the staff list before trying this invitation again.` and return to/refresh the directory rather than re-posting automatically.

- [ ] Run the new widget tests and confirm they fail before implementation.

Run: `flutter test test/management_staff_detail_page_test.dart test/management_staff_invite_page_test.dart test/management_staff_devices_page_test.dart`

- [ ] Implement `ManagementStaffDetailPage` with repository and device-identity injection.

Load devices only when `session.hasPermission('device.manage')`. Gate role/account-status controls only on `account.manage`. Use exact sets from the domain file for picker values. Disable self role change, self lock/inactivation, and self device revocation. After each successful mutation, call the staff reload callback and reload devices before displaying success.

For device status labels and actions:

```dart
final actionLabel = switch ((device.status, requestedStatus)) {
  ('pending', 'active') => 'Approve phone',
  ('active', 'revoked') => 'Revoke phone',
  ('revoked', 'active') => 'Restore phone',
  _ => 'Keep current status',
};
```

No-op choices are disabled in the UI even though the backend safely supports them.

- [ ] Implement `ManagementStaffInvitePage` and directory navigation.

Show the invite action only with `account.manage`. Submit once per explicit tap, disable the button while pending, and pop the created account only after a 201 response parses successfully. The directory inserts or reloads that account by UUID. On an uncertain result, force a directory refresh before enabling another explicit invitation attempt.

- [ ] Re-run focused widget tests, format, and analyze.

Run: `dart format lib/src/features/management/management_staff_detail_page.dart lib/src/features/management/management_staff_invite_page.dart lib/src/features/management/management_staff_devices_page.dart test/management_staff_detail_page_test.dart test/management_staff_invite_page_test.dart test/management_staff_devices_page_test.dart`

Run: `flutter test test/management_staff_detail_page_test.dart test/management_staff_invite_page_test.dart test/management_staff_devices_page_test.dart`

Run: `flutter analyze --fatal-infos`

Expected: tests pass with no overflow or analyzer findings.

- [ ] Check and commit only the Task 9 files.

Run: `git diff --check`

Run: `git add gilbic_mobile/lib/src/features/management/management_staff_detail_page.dart gilbic_mobile/lib/src/features/management/management_staff_invite_page.dart gilbic_mobile/lib/src/features/management/management_staff_devices_page.dart gilbic_mobile/test/management_staff_detail_page_test.dart gilbic_mobile/test/management_staff_invite_page_test.dart gilbic_mobile/test/management_staff_devices_page_test.dart`

Run: `git commit -m "feat: administer staff accounts and devices"`

---

### Task 10: Complete full verification, independent review, and the mobile Draft PR

**Files:**

- Modify only for verified defects: files already listed in Tasks 6-9.
- No deployment files expected.

- [ ] Run the complete Flutter suite and analyzer.

Run: `flutter test`

Run: `flutter analyze --fatal-infos`

Working directory: `gilbic_mobile`

Expected: all Flutter tests pass and analysis reports no issues.

- [ ] Run the repository's full Core validation locally without protected services.

Run from repository root: `python -m compileall -q spina_app gilbic_backend/src spina_backend_mobile/src`

Run: `python -m pytest -q gilbic_backend/tests spina_backend_mobile/tests`

Run: `git diff --check`

Expected: Python compilation and all local suites pass; only the documented disposable-PostgreSQL skips are acceptable.

- [ ] Build a review APK in a disposable generated Android host, matching `.github/workflows/spina-ci.yml`, only when at least 6 GB free is verified. Do not overwrite or add an Android host tree inside `gilbic_mobile`.

Run the workflow-dispatch `SPINA Core Validation` with `upload_apk=true` after the Draft PR exists if local host generation would consume the user's working tree. Verify the artifact contains both `lib/arm64-v8a/libflutter.so` and `lib/x86_64/libflutter.so`.

- [ ] Perform an independent code review against the approved spec before publication.

Review `codex/ca2-device-approval-api..HEAD` for permission leaks, identity exposure, stale-response races, accidental mutation retry, self-action gaps, missing confirmation consequences, and 360x640/1.3 text-scale overflows. Fix only evidenced defects, add a regression test first, rerun the focused test, then rerun the complete Flutter suite.

- [ ] Confirm the mobile branch contains only intended commits.

Run: `git status --short --branch`

Run: `git log --oneline codex/ca2-device-approval-api..HEAD`

Run: `git diff --stat codex/ca2-device-approval-api...HEAD`

Expected: only mobile CA2 commits are listed; the two unrelated backend files remain unstaged and absent from the diff.

- [ ] Push without force and create the stacked Draft PR.

Run: `git push -u origin codex/ca2-staff-device-admin`

Run:

```powershell
gh pr create --draft --base codex/ca2-device-approval-api --head codex/ca2-staff-device-admin --title "CA2: add protected staff and device administration" --body "Adds the approved permission-aware Flutter staff directory, invitation, account controls, Collector device approval/replacement UX, pending-device login guidance, strict response parsing, authoritative reloads, and accessibility-sized widget coverage. This PR is stacked on the CA2 backend Draft PR. It does not merge, deploy, restart protected services, or touch live data."
```

- [ ] Verify both Draft PR relationships and all five Core validation lanes: Python compile, backend/database tests, Flutter analyze, Flutter tests, and Android APK build/ABI verification.

Run: `gh pr view codex/ca2-staff-device-admin --json number,url,isDraft,baseRefName,headRefName,statusCheckRollup`

Run: `gh pr checks codex/ca2-staff-device-admin --watch`

Expected: the mobile PR is Draft with backend branch as base, and all required checks pass. Do not merge either PR.

- [ ] Update Master Issue #296, the linked Notion release page, and Create State with the same factual evidence.

Record branch names, Draft PR URLs, exact base/head relationships, commit SHAs, test counts, PostgreSQL execution-or-skip status, CI run URLs, APK artifact/ABI evidence, and the unchanged restrictions: no merge, no deploy, no protected restart, no migration, no live database action. Mark CA2 complete only when the two Draft PRs and required evidence exist. Keep CB1 and the explicitly deferred offline outbox/quarantine, PIN/biometric step-up, generic audit browser, and generic nonfinancial idempotency claims open.

- [ ] Finish with a clean-scope check.

Run: `git diff --check`

Run: `git status --short --branch`

Expected: no CA2 implementation file is unstaged or uncommitted; only the two preserved unrelated modifications may remain.

## Final Acceptance Checklist

- [ ] Unknown Collector Android/iOS device login commits exactly one pending row, returns HTTP 403 `device_approval_required`, and returns no tokens.
- [ ] Active and revoked device behavior remains correct; non-Collector and non-mobile behavior is unchanged.
- [ ] Staff directory reads work with either read permission, filter in PostgreSQL before paging, order deterministically, and expose no external auth identity.
- [ ] Invite/role/account-status mutations require `account.manage`; device reads/mutations require `device.manage`.
- [ ] Collector mobile approval leaves at most one active mobile device, writes exact audits, avoids duplicate no-op audits, and rolls back status changes when audit insertion fails.
- [ ] Flutter search ignores stale responses, deduplicates paging by UUID, distinguishes load/error/empty/filtered-empty/permission states, and never renders raw identity values.
- [ ] Flutter mutations are confirmed, online-only, non-optimistic, never auto-retried, and followed by authoritative reload.
- [ ] Dashboard keeps six groups and exposes `Staff & devices` first in `People, access & requests` for either permission.
- [ ] Focused and full Python/Flutter suites pass; real PostgreSQL evidence is accurately reported; Android artifact covers arm64-v8a and x86_64.
- [ ] Both PRs remain Draft and stacked correctly; Master Issue #296, Notion, and Create State match GitHub evidence.
- [ ] No merge, deployment, protected restart, migration, protected/live database operation, or unrelated-file staging occurred.
