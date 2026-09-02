# Cross-Platform Four-Role MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a controlled-data SPINA MVP with usable Client, Employee, Collector, and Management experiences on a hosted responsive PWA/Windows app mode, the existing Flutter Android/iOS app, and the existing FastAPI/Supabase/PostgreSQL backend.

**Architecture:** Keep `gilbic_backend` as the only application and financial API and `gilbic_mobile` as the native Android/iOS client. Add a dependency-light static PWA for Web and PC that calls canonical `/api/v1/...` routes, plus a Vercel ASGI entrypoint and deployment configuration. Browser and Flutter clients never access lending/accounting tables directly.

**Tech Stack:** FastAPI, Python 3.12+, PostgreSQL 17/Supabase Auth, plain HTML/CSS/ES modules/PWA, PowerShell Windows app-mode installer, Flutter/Dart Android+iOS, Vercel.

**Spec:** `docs/superpowers/specs/2026-09-03-cross-platform-four-role-mvp-design.md`

## Global Constraints

- Use only disposable/demo records during MVP validation.
- Keep FastAPI/PostgreSQL authoritative for roles, permissions, balances, receipts, allocation, remittance, and audit.
- Use canonical `/api/v1/...` routes from Web/PC; retain existing mobile aliases only for the Flutter client.
- Do not expose Supabase secret/service-role keys or PostgreSQL credentials in any public client.
- Do not connect browser code directly to `core`, `lending`, `accounting`, or `mobile` tables.
- Collector financial writes are online-only and never automatically retried after uncertainty.
- Keep Regular and 7x7 values and results visibly separate.
- Do not weaken existing Management review/prepare/post/reversal controls.
- A real GCash checkout/proof is not an official payment until protected provider settlement verification exists.
- Android and iOS share the existing Flutter business adapters; native iOS signing requires macOS/Xcode and Apple credentials.

---

### Task 1: Add deployable FastAPI entrypoint and hosting contract

**Files:**
- Create: `api/index.py`
- Create: `requirements.txt`
- Create: `vercel.json`
- Create: `tests/test_vercel_entrypoint.py`
- Modify: `gilbic_backend/src/gilbic_backend/main.py`

**Interfaces:**
- Consumes: existing `gilbic_backend.main.app` ASGI application.
- Produces: root-level importable `api.index:app`, static portal routing, and explicit CORS middleware configured by `GILBIC_CORS_ORIGINS`.

- [ ] **Step 1: Write the failing entrypoint and CORS tests**

```python
from fastapi.testclient import TestClient


def test_vercel_entrypoint_exports_existing_fastapi_app():
    from api.index import app

    response = TestClient(app).get('/health/live')
    assert response.status_code == 200
    assert response.json()['service'] == 'gilbic-backend'


def test_preflight_allows_configured_portal_origin(monkeypatch):
    monkeypatch.setenv('GILBIC_CORS_ORIGINS', 'https://portal.example')
    from gilbic_backend.config import get_settings
    get_settings.cache_clear()
    from gilbic_backend.main import create_app

    response = TestClient(create_app()).options(
        '/api/v1/meta',
        headers={
            'Origin': 'https://portal.example',
            'Access-Control-Request-Method': 'GET',
        },
    )
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'https://portal.example'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m pytest -q tests/test_vercel_entrypoint.py
```

Expected: import failure for `api.index` and missing CORS header.

- [ ] **Step 3: Add CORS middleware in `create_app()`**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=[
        'Authorization',
        'Content-Type',
        'Idempotency-Key',
        'X-App-Platform',
        'X-App-Version',
        'X-Client-Transaction-Id',
        'X-Device-Id',
        'X-Gilbic-Contract-Version',
    ],
)
```

- [ ] **Step 4: Add `api/index.py`**

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for package_root in (ROOT / 'gilbic_backend' / 'src', ROOT / 'spina_backend_mobile' / 'src'):
    value = str(package_root)
    if value not in sys.path:
        sys.path.insert(0, value)

from gilbic_backend.main import app

__all__ = ['app']
```

- [ ] **Step 5: Add root dependencies and routing**

`requirements.txt` must pin the existing backend dependency ranges and include no frontend secrets. `vercel.json` must serve `spina_portal/` as static output and rewrite `/api/*` plus `/health/*` to `api/index.py` while preserving the original request path.

- [ ] **Step 6: Run the entrypoint tests**

Run:

```powershell
$env:PYTHONPATH = "gilbic_backend/src;spina_backend_mobile/src;."
python -m pytest -q tests/test_vercel_entrypoint.py
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add api/index.py requirements.txt vercel.json tests/test_vercel_entrypoint.py gilbic_backend/src/gilbic_backend/main.py
git commit -m "feat: add deployable SPINA API entrypoint"
```

### Task 2: Build the shared PWA shell, API client, and session boundary

**Files:**
- Create: `spina_portal/index.html`
- Create: `spina_portal/assets/app.css`
- Create: `spina_portal/assets/config.js`
- Create: `spina_portal/assets/api.js`
- Create: `spina_portal/assets/session.js`
- Create: `spina_portal/assets/app.js`
- Create: `spina_portal/manifest.webmanifest`
- Create: `spina_portal/sw.js`
- Create: `spina_portal/tests/session.test.mjs`
- Create: `spina_portal/tests/api.test.mjs`
- Create: `package.json`

**Interfaces:**
- Produces: `SpinaApi`, `SessionStore`, `renderApp()`, and installable PWA assets.
- `SpinaApi.login(identifier, password)` sends `{username, password, device_id, platform:'web', app_version}` to `/api/v1/auth/login`.
- `SpinaApi.request(path, options)` adds bearer/device headers, parses the standard `{success,data,error}` envelope, and emits `spina:unauthorized` on HTTP 401.

- [ ] **Step 1: Add Node tests for session and request behavior**

Test exact rules: access tokens use `sessionStorage`, device ID persists in `localStorage`, login never stores a token after 403, and financial requests do not automatically retry.

- [ ] **Step 2: Run tests and observe missing modules**

```bash
node --test spina_portal/tests/*.test.mjs
```

Expected: module-not-found failures.

- [ ] **Step 3: Implement `SessionStore` and `SpinaApi`**

Use Web Crypto `crypto.randomUUID()` for the browser device ID. Normalize server errors to `{status, code, message, data}`. Refresh a session only on an explicit caller action; never retry POST requests silently.

- [ ] **Step 4: Implement the responsive application shell**

The shell must contain:

- login form;
- optional Client registration form;
- top status bar with environment, online/offline, role, refresh, and logout;
- responsive side/bottom navigation;
- main content region with `aria-live` status;
- error banner and permission-denied card;
- four role dashboard mount points.

- [ ] **Step 5: Add PWA manifest and safe service worker**

Cache only immutable shell assets. Do not cache authenticated API responses, receipts, balances, routes, or user-specific pages.

- [ ] **Step 6: Run Node tests**

```bash
node --test spina_portal/tests/*.test.mjs
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add package.json spina_portal
git commit -m "feat: add secure four-role SPINA PWA shell"
```

### Task 3: Implement usable Client portal flows

**Files:**
- Create: `spina_portal/assets/roles/client.js`
- Create: `spina_portal/tests/client-role.test.mjs`
- Modify: `spina_portal/assets/app.js`

**Interfaces:**
- Consumes: `SpinaApi.request` and authenticated Client session.
- Produces: Client navigation with Profile, Loans, Payment Timeline/Receipts, Notifications, Renewal, Support, and Payment Instructions.

- [ ] **Step 1: Write tests for own-account route mapping and safe empty states**

Assert that Client code calls only Client/self endpoints and never a Management or Collector endpoint. Verify Regular and 7x7 cards are separate.

- [ ] **Step 2: Run tests and verify failure**

```bash
node --test spina_portal/tests/client-role.test.mjs
```

- [ ] **Step 3: Implement Client dashboard loaders**

Map to the existing canonical Client APIs discovered in backend route modules. Render only returned fields and official receipt links/data. Add request forms only for endpoints that already exist.

- [ ] **Step 4: Add registration flow**

Submit `/api/v1/auth/register` with username, email, full name, claimed client code, phone, and password. Show the server's pending-Management-approval message and do not assume registration equals active access.

- [ ] **Step 5: Run tests**

```bash
node --test spina_portal/tests/client-role.test.mjs
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add spina_portal/assets/roles/client.js spina_portal/assets/app.js spina_portal/tests/client-role.test.mjs
git commit -m "feat: add usable Client web portal"
```

### Task 4: Implement usable Collector route and collection flow

**Files:**
- Create: `spina_portal/assets/roles/collector.js`
- Create: `spina_portal/assets/uuid.js`
- Create: `spina_portal/tests/collector-role.test.mjs`
- Modify: `spina_portal/assets/app.js`

**Interfaces:**
- `loadCollectorRoute()` calls `/api/v1/collector/routes/today`.
- `buildCollectionSubmission(entry, form, device)` produces the exact official collection body and headers.
- `submitCollection()` calls `/api/v1/collector/collections` once with identical body/header UUIDs and contract version `1`.

- [ ] **Step 1: Write request-formation tests**

Use a fixed UUID and date. Assert body/header idempotency identity matches, `device_sequence >= 1`, route revision is included, and entry types are `payment` or `pass` exactly as defined by the current backend contract.

- [ ] **Step 2: Run tests and verify failure**

```bash
node --test spina_portal/tests/collector-role.test.mjs
```

- [ ] **Step 3: Implement ledger-first route UI**

Group entries by `area`. Display Client, loan type, daily amount, remaining balance, contract unpaid amount, PASS count, ADV coverage, status, notes, and today's receipt. Keep Regular and 7x7 visually distinct.

- [ ] **Step 4: Implement Payment and unable-to-pay forms**

Disable entry when `can_enter_payment` is false. For payment require positive amount. For PASS require no amount. Use Philippine business date from the route date and an ISO UTC `recorded_at` timestamp.

- [ ] **Step 5: Implement uncertainty lock**

After a network error or response without a definitive accepted/duplicate/rejected result, disable further collection submission, retain the request identity in memory, and require route refresh before unlocking. Do not automatic-retry.

- [ ] **Step 6: Render official result and refresh route**

On accepted/duplicate, display the server receipt/result and then reload `/api/v1/collector/routes/today`.

- [ ] **Step 7: Run tests**

```bash
node --test spina_portal/tests/collector-role.test.mjs
```

- [ ] **Step 8: Commit**

```bash
git add spina_portal/assets/roles/collector.js spina_portal/assets/uuid.js spina_portal/assets/app.js spina_portal/tests/collector-role.test.mjs
git commit -m "feat: add usable Collector web route and payment flow"
```

### Task 5: Implement usable Employee and Management experiences

**Files:**
- Create: `spina_portal/assets/roles/employee.js`
- Create: `spina_portal/assets/roles/management.js`
- Create: `spina_portal/tests/employee-role.test.mjs`
- Create: `spina_portal/tests/management-role.test.mjs`
- Modify: `spina_portal/assets/app.js`

**Interfaces:**
- Employee renders only routes whose permission appears in the authenticated session.
- Management loads `/api/v1/management/dashboard-overview` and offers existing review/list destinations only when exact permission checks pass.

- [ ] **Step 1: Write permission-filter tests**

Assert Employee never receives Collector collection actions or Management protected actions. Assert Management dashboard requires `management.dashboard.view` and destination visibility is permission-driven.

- [ ] **Step 2: Run tests and verify failure**

```bash
node --test spina_portal/tests/employee-role.test.mjs spina_portal/tests/management-role.test.mjs
```

- [ ] **Step 3: Implement Employee dashboard**

Sections: My workday, Pay & requests, Office functions, Updates & account. Display connected functions only when both implemented and permitted. Display unconnected attendance/payroll/leave as clear unavailable cards with no mutation controls.

- [ ] **Step 4: Implement Management dashboard**

Load live overview metrics, alerts/audit, loan portfolio/search, registration approvals, renewals, support, remittances, staff/devices, and accounting launchers through existing APIs. Protected actions must show source/current status/warnings/consequence and require an explicit confirmation; no generic direct database action exists.

- [ ] **Step 5: Run tests**

```bash
node --test spina_portal/tests/employee-role.test.mjs spina_portal/tests/management-role.test.mjs
```

- [ ] **Step 6: Commit**

```bash
git add spina_portal/assets/roles/employee.js spina_portal/assets/roles/management.js spina_portal/assets/app.js spina_portal/tests/employee-role.test.mjs spina_portal/tests/management-role.test.mjs
git commit -m "feat: add usable Employee and Management web workspaces"
```

### Task 6: Add Windows app-mode installation and native mobile build controls

**Files:**
- Create: `spina_pc/install_spina_pc.ps1`
- Create: `spina_pc/uninstall_spina_pc.ps1`
- Create: `spina_pc/README.md`
- Create: `gilbic_mobile/tool/bootstrap_all_platforms.ps1`
- Modify: `gilbic_mobile/README.md`
- Create: `tests/test_platform_bootstrap_contract.py`

**Interfaces:**
- Windows installer takes `-PortalUrl` and creates a Start Menu/Desktop shortcut using Edge or Chrome `--app=<url>`.
- Flutter bootstrap generates Android and iOS only for the native MVP and reports unsupported native signing prerequisites honestly.

- [ ] **Step 1: Write static contract tests**

Assert installer never embeds credentials, uses HTTPS unless localhost, and the Flutter script runs analyze/test before build commands.

- [ ] **Step 2: Implement installer/uninstaller**

Detect `msedge.exe`, then `chrome.exe`; fail with a clear message when neither exists. Create shortcut through `WScript.Shell` with a SPINA application name and icon fallback.

- [ ] **Step 3: Implement repeatable Flutter build script**

Run `flutter create --platforms=android,ios`, `flutter pub get`, `flutter analyze --fatal-infos`, `flutter test`, and optional `flutter build apk --debug`. Do not claim an iOS native build on Windows.

- [ ] **Step 4: Run tests**

```bash
python -m pytest -q tests/test_platform_bootstrap_contract.py
```

- [ ] **Step 5: Commit**

```bash
git add spina_pc gilbic_mobile/tool/bootstrap_all_platforms.ps1 gilbic_mobile/README.md tests/test_platform_bootstrap_contract.py
git commit -m "feat: add Windows app mode and mobile build controls"
```

### Task 7: Add reviewed Supabase private-schema barrier and demo bootstrap

**Files:**
- Create: `gilbic_backend/sql/0109_mvp_private_schema_barrier.sql`
- Create: `tools/run_mvp_private_schema_barrier_validation.py`
- Create: `gilbic_backend/tests/test_mvp_private_schema_barrier.py`
- Create: `docs/security/mvp-supabase-boundary.md`

**Interfaces:**
- Migration revokes `anon`/`authenticated` access to private schemas/tables/sequences without changing owner/backend privileges or bulk-enabling RLS.
- Validation proves public roles cannot directly select/update a representative lending/accounting table while the backend database role remains usable.

- [ ] **Step 1: Write migration-contract tests**

Assert the migration covers `core`, `lending`, `accounting`, and `mobile`, includes default privileges, and contains no `GRANT ... TO anon/authenticated` or blanket `DISABLE ROW LEVEL SECURITY` statement.

- [ ] **Step 2: Run tests and verify failure**

```bash
python -m pytest -q gilbic_backend/tests/test_mvp_private_schema_barrier.py
```

- [ ] **Step 3: Write the migration and validation script**

Use explicit `REVOKE USAGE`, `REVOKE ALL PRIVILEGES ON ALL TABLES`, `REVOKE ALL PRIVILEGES ON ALL SEQUENCES`, and `ALTER DEFAULT PRIVILEGES` statements. The script must run against disposable PostgreSQL first and print exact privilege evidence.

- [ ] **Step 4: Run disposable validation**

```bash
python tools/run_mvp_private_schema_barrier_validation.py
```

Expected: representative public-role reads/writes denied and backend-owner health query succeeds.

- [ ] **Step 5: Commit**

```bash
git add gilbic_backend/sql/0109_mvp_private_schema_barrier.sql tools/run_mvp_private_schema_barrier_validation.py gilbic_backend/tests/test_mvp_private_schema_barrier.py docs/security/mvp-supabase-boundary.md
git commit -m "security: isolate MVP financial schemas from public clients"
```

### Task 8: End-to-end verification, deployment, and exact checkpoint

**Files:**
- Create: `docs/release/cross-platform-four-role-mvp-acceptance.md`
- Modify: `.github/workflows/spina-ci.yml`
- Modify: `.github/workflows/spina-security-compliance.yml`
- Modify: `README.md`

**Interfaces:**
- Produces exact-commit evidence for backend, PWA, Windows installer, Android build, shared iOS code, role isolation, and Supabase boundary.

- [ ] **Step 1: Add CI lanes for root API/PWA tests**

Run Python entrypoint tests and `node --test spina_portal/tests/*.test.mjs`. Existing backend and Flutter suites remain authoritative and must not be duplicated unnecessarily.

- [ ] **Step 2: Run complete local/static verification**

```powershell
$env:PYTHONPATH = "gilbic_backend/src;spina_backend_mobile/src;."
python -m pytest -q tests gilbic_backend/tests spina_backend_mobile/tests
node --test spina_portal/tests/*.test.mjs
cd gilbic_mobile
flutter analyze --fatal-infos
flutter test
```

Record exact pass/skip/failure counts. Do not convert environment-dependent skips into passes.

- [ ] **Step 3: Deploy preview**

Configure Vercel environment variables server-side, deploy the branch, and verify:

```text
GET /                  -> 200 HTML login shell
GET /health/live       -> 200 gilbic-backend
GET /health/ready      -> 200 only when database is reachable
GET /api/v1/meta       -> 200 metadata
```

- [ ] **Step 4: Run four-role controlled acceptance**

Use controlled demo accounts. Prove Client own-data isolation, Employee permission isolation, Collector authoritative route/payment/receipt, and Management overview visibility. Record limitations and omit credentials from repository evidence.

- [ ] **Step 5: Create Draft PR and update project records**

Create a Draft PR into the exact stacked base, attach verification evidence, and update Master Issue #296, Notion Project Memory, and Create State. Keep the branch unmerged and non-production until Management approves the MVP.

- [ ] **Step 6: Final commit**

```bash
git add docs/release/cross-platform-four-role-mvp-acceptance.md .github/workflows README.md
git commit -m "test: prove four-role cross-platform MVP"
```
