# SPINA MVP Backend, Security, and Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the existing FastAPI application as the sole MVP API, enforce explicit CORS, and commit a disposable-tested Supabase private-schema access barrier without creating a second backend.

**Architecture:** Add a root ASGI adapter that imports `gilbic_backend.main:app`, install the nested backend package through a root requirements file, configure CORS from existing `GILBIC_CORS_ORIGINS`, and revoke Supabase Data API roles from server-owned schemas through migration `0109`. No live migration is applied by this plan.

**Tech Stack:** Python 3.12+, FastAPI, Starlette CORS middleware, Psycopg 3, PostgreSQL 17/Supabase, pytest, Vercel Python runtime.

**Spec:** `docs/superpowers/specs/2026-09-03-cross-platform-mvp-design.md`

## Global Constraints

- FastAPI/PostgreSQL remains the only official application and financial authority.
- Supabase Auth proves identity; FastAPI resolves application roles, permissions, account status, and applicable device state.
- Public clients never receive a Supabase secret/service-role key or PostgreSQL URL.
- Credentialed wildcard CORS is prohibited.
- Private-schema access revocation is committed and proven on disposable PostgreSQL before any protected/live application.
- Opening the PR, running CI, or deploying a preview must not post financial records or mutate production data.

---

### Task 1: Prove and add the deployable ASGI adapter

**Files:**
- Create: `gilbic_backend/tests/test_vercel_entrypoint.py`
- Create: `app.py`
- Create: `requirements.txt`

**Interfaces:**
- Consumes: `gilbic_backend.main.app`.
- Produces: root module variable `app: FastAPI` for Vercel discovery and `requirements.txt` that installs `./gilbic_backend`.

- [ ] **Step 1: Write the failing entrypoint test**

```python
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from fastapi import FastAPI


def test_root_vercel_entrypoint_exports_existing_fastapi_app() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "app.py"
    spec = spec_from_file_location("spina_vercel_entrypoint", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    assert isinstance(module.app, FastAPI)
    paths = module.app.openapi()["paths"]
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "/api/v1/meta" in paths


def test_root_requirements_installs_existing_backend_package() -> None:
    root = Path(__file__).resolve().parents[2]
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    assert requirements.splitlines() == ["./gilbic_backend"]
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_vercel_entrypoint.py
```

Expected: failure because `app.py` and root `requirements.txt` do not exist.

- [ ] **Step 3: Add the minimal adapter and dependency file**

`app.py`:

```python
from gilbic_backend.main import app

__all__ = ["app"]
```

`requirements.txt`:

```text
./gilbic_backend
```

- [ ] **Step 4: Verify import and health routes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_vercel_entrypoint.py gilbic_backend\tests\test_app.py
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app.py requirements.txt gilbic_backend/tests/test_vercel_entrypoint.py
git commit -m "feat: expose FastAPI for Vercel deployment"
```

### Task 2: Enforce explicit CORS from existing settings

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/main.py`
- Modify: `gilbic_backend/tests/test_app.py`

**Interfaces:**
- Consumes: `Settings.cors_origin_list` from `config.py`.
- Produces: credentialed CORS for explicit origins only, with `Authorization`, `Content-Type`, `X-Device-Id`, `X-App-Platform`, and `X-App-Version` request headers.

- [ ] **Step 1: Add failing CORS tests**

```python
from fastapi.testclient import TestClient


def test_configured_web_origin_receives_cors_headers(monkeypatch) -> None:
    monkeypatch.setenv("GILBIC_CORS_ORIGINS", "https://mvp.spina.example")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        response = client.options(
            "/api/v1/meta",
            headers={
                "Origin": "https://mvp.spina.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,x-device-id",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == (
            "https://mvp.spina.example"
        )
        assert response.headers["access-control-allow-credentials"] == "true"
    finally:
        get_settings.cache_clear()


def test_unconfigured_origin_receives_no_cors_authorization(monkeypatch) -> None:
    monkeypatch.setenv("GILBIC_CORS_ORIGINS", "https://mvp.spina.example")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        response = client.get(
            "/api/v1/meta",
            headers={"Origin": "https://attacker.example"},
        )
        assert "access-control-allow-origin" not in response.headers
    finally:
        get_settings.cache_clear()
```

Import `get_settings` from `gilbic_backend.config` in the test module.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_app.py -k cors
```

Expected: configured origin test fails because the application has no CORS middleware.

- [ ] **Step 3: Add CORS middleware once in `create_app()`**

```python
from fastapi.middleware.cors import CORSMiddleware

# immediately after app = FastAPI(...)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Device-Id",
        "X-App-Platform",
        "X-App-Version",
    ],
)
```

Do not allow `*` when credentials are enabled.

- [ ] **Step 4: Run focused and complete backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_app.py
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests spina_backend_mobile\tests
```

Expected: all available non-database tests pass; configured database tests are either passed by the disposable lane or remain explicitly skipped when their required URL is absent.

- [ ] **Step 5: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/main.py gilbic_backend/tests/test_app.py
git commit -m "security: restrict API CORS origins"
```

### Task 3: Revoke Supabase Data API roles from private schemas

**Files:**
- Create: `gilbic_backend/sql/0109_revoke_private_schema_data_api_access.sql`
- Create: `gilbic_backend/tests/test_private_schema_data_api_barrier.py`

**Interfaces:**
- Consumes: PostgreSQL roles `anon` and `authenticated` when present; schemas `core`, `lending`, `accounting`, and `mobile` when present.
- Produces: idempotent revocation of schema, table, sequence, and function privileges plus matching default privileges for the migration owner.

- [ ] **Step 1: Write failing static and PostgreSQL tests**

```python
from pathlib import Path

import os
import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "gilbic_backend/sql/0109_revoke_private_schema_data_api_access.sql"


def test_private_schema_barrier_covers_all_server_owned_schemas() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    for schema in ("core", "lending", "accounting", "mobile"):
        assert schema in sql
    for role in ("anon", "authenticated"):
        assert role in sql
    assert "REVOKE ALL PRIVILEGES ON ALL TABLES" in sql
    assert "REVOKE ALL PRIVILEGES ON ALL SEQUENCES" in sql
    assert "REVOKE EXECUTE ON ALL FUNCTIONS" in sql
    assert "ALTER DEFAULT PRIVILEGES" in sql


@pytest.mark.skipif(
    not os.getenv("GILBIC_TEST_DATABASE_URL"),
    reason="requires disposable PostgreSQL",
)
def test_private_schema_barrier_removes_direct_data_api_access() -> None:
    url = os.environ["GILBIC_TEST_DATABASE_URL"]
    sql = MIGRATION.read_text(encoding="utf-8")
    with psycopg.connect(url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS mvp_barrier_probe CASCADE")
            cursor.execute("CREATE SCHEMA mvp_barrier_probe")
            cursor.execute("CREATE TABLE mvp_barrier_probe.sample(id bigserial primary key)")
            cursor.execute("CREATE FUNCTION mvp_barrier_probe.ping() RETURNS int LANGUAGE sql AS 'SELECT 1'")
            cursor.execute("GRANT USAGE ON SCHEMA mvp_barrier_probe TO anon, authenticated")
            cursor.execute("GRANT ALL ON ALL TABLES IN SCHEMA mvp_barrier_probe TO anon, authenticated")
            cursor.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA mvp_barrier_probe TO anon, authenticated")
            cursor.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA mvp_barrier_probe TO anon, authenticated")
```

The final integration test uses the same revocation helper logic against `mvp_barrier_probe` in a transaction-local generated copy, then asserts `has_schema_privilege`, `has_table_privilege`, `has_sequence_privilege`, and `has_function_privilege` are false for both roles. The production migration itself targets only the four approved private schemas.

- [ ] **Step 2: Run the static test and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_private_schema_data_api_barrier.py
```

Expected: failure because migration `0109` does not exist.

- [ ] **Step 3: Implement the idempotent migration**

```sql
BEGIN;

DO $$
DECLARE
    target_role text;
    target_schema text;
BEGIN
    FOREACH target_role IN ARRAY ARRAY['anon', 'authenticated']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = target_role) THEN
            FOREACH target_schema IN ARRAY ARRAY['core', 'lending', 'accounting', 'mobile']
            LOOP
                IF EXISTS (
                    SELECT 1 FROM pg_namespace WHERE nspname = target_schema
                ) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM %I',
                        target_schema,
                        target_role
                    );
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM %I',
                        target_schema,
                        target_role
                    );
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM %I',
                        target_schema,
                        target_role
                    );
                    EXECUTE format(
                        'REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA %I FROM %I',
                        target_schema,
                        target_role
                    );
                    EXECUTE format(
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL ON TABLES FROM %I',
                        target_schema,
                        target_role
                    );
                    EXECUTE format(
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL ON SEQUENCES FROM %I',
                        target_schema,
                        target_role
                    );
                    EXECUTE format(
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE EXECUTE ON FUNCTIONS FROM %I',
                        target_schema,
                        target_role
                    );
                END IF;
            END LOOP;
        END IF;
    END LOOP;
END
$$;

COMMIT;
```

- [ ] **Step 4: Verify static, migration-boundary, and disposable tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_private_schema_data_api_barrier.py gilbic_backend\tests\test_disposable_validation_migration_boundaries.py
```

Then run the repository's Financial & Database workflow with a disposable PostgreSQL cluster. Expected: migration is idempotent, absent roles/schemas do not fail installation, and both Supabase Data API roles lack direct privileges afterward.

- [ ] **Step 5: Commit**

```bash
git add gilbic_backend/sql/0109_revoke_private_schema_data_api_access.sql gilbic_backend/tests/test_private_schema_data_api_barrier.py
git commit -m "security: block direct Data API access to private schemas"
```

### Task 4: Add deployment configuration contract and HTTP smoke

**Files:**
- Create: `vercel.json`
- Modify: `gilbic_backend/tests/test_vercel_entrypoint.py`
- Create: `tools/smoke_mvp_api.py`
- Create: `gilbic_backend/tests/test_smoke_mvp_api.py`

**Interfaces:**
- Consumes: root `app.py`, environment variable `SPINA_MVP_API_URL` for smoke execution.
- Produces: Vercel FastAPI max duration and an HTTP checker for liveness, readiness, and metadata.

- [ ] **Step 1: Write failing configuration and smoke tests**

```python
import json
from pathlib import Path

from tools.smoke_mvp_api import expected_smoke_paths


def test_vercel_config_targets_root_fastapi_entrypoint() -> None:
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "vercel.json").read_text(encoding="utf-8"))
    assert config["functions"]["app.py"]["maxDuration"] == 60


def test_smoke_paths_cover_live_ready_and_meta() -> None:
    assert expected_smoke_paths() == (
        "/health/live",
        "/health/ready",
        "/api/v1/meta",
    )
```

- [ ] **Step 2: Run and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_vercel_entrypoint.py gilbic_backend\tests\test_smoke_mvp_api.py
```

Expected: failure because `vercel.json` and smoke module do not exist.

- [ ] **Step 3: Add configuration and smoke implementation**

`vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "app.py": {
      "maxDuration": 60
    }
  }
}
```

`tools/smoke_mvp_api.py` exposes `expected_smoke_paths()` and a `main()` that requires `SPINA_MVP_API_URL`, sends GET requests with a 15-second timeout, requires HTTP 200 for live/meta and 200 for ready, validates JSON service names, and exits nonzero on any mismatch. It prints no tokens, keys, database URLs, or response headers containing credentials.

- [ ] **Step 4: Run local API smoke and hosted preview smoke**

Run:

```powershell
$env:SPINA_MVP_API_URL = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe tools\smoke_mvp_api.py
```

After Vercel preview deployment, repeat with the preview base URL. Expected: all three endpoints pass.

- [ ] **Step 5: Commit**

```bash
git add vercel.json tools/smoke_mvp_api.py gilbic_backend/tests/test_vercel_entrypoint.py gilbic_backend/tests/test_smoke_mvp_api.py
git commit -m "deploy: add FastAPI preview smoke contract"
```

## Completion checkpoint

This plan is complete only when the root FastAPI adapter imports, explicit CORS tests pass, migration `0109` passes static and disposable PostgreSQL proof, Vercel preview contains an actual application, and the three HTTP smoke endpoints return the expected responses. No live database migration or production deployment is implied.