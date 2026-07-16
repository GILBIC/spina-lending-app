# SPINA code issue review

This document tracks the current code-health findings and a safe improvement plan for the SPINA desktop PostgreSQL app.

## Current status

The hardcoded PostgreSQL password was already removed from the current GitHub `main` branch. The app now expects the password from the Windows environment variable `SPINA_PG_PASSWORD`.

The remaining concerns are mostly about reliability, maintainability, and performance risk. They should be fixed in small pull requests because the app contains many patch layers and a large amount of business logic in one file.

## Priority findings

### High priority

1. **Patch-chain architecture**
   - Multiple methods are assigned after class creation.
   - `App.__init__`, dashboard refresh, collector refresh, role access, reports, and themes are especially sensitive.
   - Risk: a small edit can be overridden later in the file or change startup order.

2. **Silent exception handling**
   - Many broad `except Exception` and pass-only handlers remain.
   - Risk: real errors can be hidden, especially in reports, database writes, backup/restore, account login, and payment import.

3. **Large UI/database functions**
   - Some functions mix SQL, business rules, Tkinter updates, and PDF/report creation.
   - Risk: slow screens, UI freezes, and hard-to-debug regressions.

### Medium priority

4. **Repeated PostgreSQL connections**
   - Storage helpers still open new PostgreSQL connections directly.
   - Risk: startup or report generation can become slower as data grows.
   - Fix later with a cautious connection-pool PR after smoke testing.

5. **Dynamic SQL patterns**
   - Some SQL uses internal dynamic table or column names.
   - Risk: not necessarily unsafe today, but harder to audit and maintain.
   - Fix by centralizing identifier whitelists and keeping values parameterized.

6. **Single huge source file**
   - The app is still one large file.
   - Risk: future features become harder to add safely.
   - Split into modules only after diagnostics and smoke tests are stable.

## New diagnostic tools

### Static quality audit

```bash
python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
```

With JSON output:

```bash
python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json quality-report.json
```

This checks for:

- duplicate top-level definitions
- duplicate class methods
- repeated monkey-patch targets
- very large functions
- broad exception handlers
- pass-only exception handlers
- dynamic SQL examples
- PostgreSQL connection call sites
- possible blocking calls

### Local startup diagnostics

Run this on the Windows PC before launching SPINA when PostgreSQL startup fails:

```bash
python tools/spina_startup_diagnostics.py
```

This checks:

- Python version
- whether `SPINA_PG_PASSWORD` is set
- whether `psycopg` is installed
- whether PostgreSQL port 5432 is reachable
- whether login to `spina_db` works

## Safe PR order

1. **Diagnostics tooling**
   - Add static audit and local startup check.
   - No app behavior changes.

2. **Critical-path logging**
   - Improve logging around login, DB connection, backup, restore, report generation, and Excel import.
   - Avoid changing loan/payment logic.

3. **Duplicate method cleanup**
   - Remove only shadowed duplicate methods that are proven identical or behavior-neutral.

4. **One-screen performance PR**
   - Start with Clients search or Collector Route refresh.
   - Avoid changing report math and balance calculations.

5. **PostgreSQL pooling PR**
   - Add connection pooling only after the above tests are stable.

## Local smoke test after every PR

1. Open app with `SPINA_PG_PASSWORD` set.
2. Login as Owner.
3. Open Dashboard.
4. Open Clients and search one client.
5. Open Reports and select one client.
6. Open Cash Control.
7. Open Collector Route and select one collector.
8. Generate one safe test PDF/report.
9. Open Backup tools.

Do not merge behavior-changing PRs until this smoke test passes.


## Phase 2 cleanup completed

Removed earlier duplicate `App` class method definitions that were shadowed inside the class body.
Python binds only the final method with a repeated name when the class is created, so this cleanup keeps the active implementations and removes inactive earlier definitions.

Removed definitions:
- `App._get_selected_report_client` earlier definition at lines 9882-9890
- `App._get_selected_report_client` earlier definition at lines 18622-18630
- `App._auto_load_report_note` earlier definition at lines 9920-9950

No monkey-patch chains, login/database logic, reports, collectors, dashboard, balances, or call sites were changed.
