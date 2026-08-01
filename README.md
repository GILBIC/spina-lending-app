# SPINA Lending Platform

SPINA is a lending and collection platform with a mature Python/Tkinter desktop application, the Gilbic Flutter mobile application, a GitHub-first FastAPI backend, and PostgreSQL/Supabase infrastructure.

## Architecture and progress

Start with the living architecture hub:

- [Whole-system map](docs/architecture/system-map.md)
- [Progress and roadmap](docs/architecture/progress-map.md)
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
| SPINA Desktop | `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`, `spina_app/` | Office operations, lending rules, Data Bank, clients, reports, routes, cash control, backups |
| Gilbic Mobile | `gilbic_mobile/` | Role-based Android/iOS experience, secure sessions/device identity, routes, collection entry |
| Gilbic Backend | `gilbic_backend/` | FastAPI, Supabase authentication integration, authorization, device enforcement, routes, official collections |
| Collection package | `spina_backend_mobile/` | Shared Payment/ADV/PASS contract and idempotent PostgreSQL boundary |
| Architecture tooling | `tools/generate_architecture_map.py`, `tools/test_architecture_map.py` | Generated desktop ownership, dependency, database, and risk maps |

## Debugging

Open a GitHub issue using the **SPINA cross-layer bug report** template. It collects the safe identifiers needed to trace a problem without exposing passwords, tokens, database credentials, Supabase secrets, or raw installation IDs.

## Current development direction

The current critical path is documented in [progress-map.md](docs/architecture/progress-map.md). Status is based on merged code and open pull requests; an open draft is not counted as complete.
