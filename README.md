# SPINA Lending Platform

SPINA is a lending and collection platform with a mature Python/Tkinter desktop application, the Gilbic Flutter mobile application, a GitHub-first FastAPI backend, and PostgreSQL/Supabase infrastructure.

## Architecture and progress

Start with the dated implementation and acceptance state, then use the architecture hub for code ownership:

- [Whole-system map](docs/architecture/system-map.md)
- [Current implementation, configuration and acceptance state](docs/release/2026-09-28-implementation-state.md)
- [Master roadmap](https://github.com/GILBIC/spina-lending-app/issues/296)
- [Archived progress map](docs/architecture/progress-map.md)
- [Cross-layer debugging playbook](docs/architecture/debugging-playbook.md)
- [Architecture hub and generated desktop maps](docs/architecture/README.md)

The repository also contains a generated static architecture map for the Desktop Python application:

- [Feature map](docs/architecture/feature-map.md)
- [Function index](docs/architecture/function-index.md)
- [Dependency map](docs/architecture/dependency-map.md)
- [Database access map](docs/architecture/database-access-map.md)
- [Risk map](docs/architecture/risk-map.md)
- [Machine-readable map](architecture-map.json)

## Main components

| Component | Location | Responsibility |
|---|---|---|
| SPINA Desktop | `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`, `spina_app/` | Current mature office workflows while the new Desktop direction moves Management and Employee work onto shared FastAPI contracts |
| Gilbic Mobile | `gilbic_mobile/` | Role-based Android/iOS experience for Client, Collector, Employee, and Management; secure sessions/device identity; protected workflows; and functional capability parity delivered incrementally through the same FastAPI permissions and official outcomes as Desktop |
| Gilbic Backend | `gilbic_backend/` | FastAPI, Supabase authentication integration, authorization, device enforcement, routes, official collections |
| Company portal | `spina_portal/` | Shared Web/Windows role workspaces using the same protected FastAPI authority |
| Collection package | `spina_backend_mobile/` | Shared Payment/ADV/PASS contract and idempotent PostgreSQL boundary |
| Architecture tooling | `tools/generate_architecture_map.py`, `tools/test_architecture_map.py` | Generated desktop ownership, dependency, database, and risk maps |

## Debugging

Open a GitHub issue using the **SPINA cross-layer bug report** template. It collects the safe identifiers needed to trace a problem without exposing passwords, tokens, database credentials, Supabase secrets, or raw installation IDs.

## Current development direction

The current critical path is documented in the [dated implementation state](docs/release/2026-09-28-implementation-state.md). It distinguishes implemented code, configuration and acceptance evidence. Issue 296 remains the master roadmap; the old progress map is archived. An open draft or passing synthetic test is not production acceptance.

The implemented Management mobile surface includes a server-authoritative live overview of portfolio, collection, cash-custody, queue, and activity facts. It requires an active approved device, the canonical Management role, and `management.dashboard.view`; specialized queue metrics are omitted unless the server grants their exact additional permission. The overview is read-only, does not calculate official balances locally, and routes into existing protected workflows that recheck permissions.

The intended cross-platform model is functional capability parity for Management and Employees across Desktop and mobile through the same GitHub-first FastAPI backend, server-derived roles and permissions, PostgreSQL records, and audit controls. Layouts may differ by device, but financial rules, approvals, official records, and permission meanings may not. Accounting, HR/payroll, and client-relationship access remain separable permission sets, with Management retaining sensitive approvals and final authorization.

The repository contains permission-scoped Employee Activity and employee-operation/payroll modules, with shared portal and mobile workspaces. Management visibility remains constrained by server permissions and owning-domain records. Actual staff identities, rates, schedules, contributions and company acceptance still require verified configuration. Employee Activity is a read-only projection and does not authorize impersonation or bypass maker-checker controls; the dated state links the remaining configuration and acceptance gates.

New Client Fund, renewal fund, and smart client capacity are intended future server-authoritative modules for office cash planning and controlled client growth. They are not totals entered by Employees, not values inferred by Flutter or Desktop UI, and not calculations performed by the live Management overview.
