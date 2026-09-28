# SPINA Lending Platform

SPINA provides shared lending, collection, Employee and Management workflows through a FastAPI backend and PostgreSQL/Supabase. Web and Windows use the company portal; Android uses the Flutter application. Native iOS delivery remains outside the current V1 release.

## Current work and architecture

- [Implementation, audit fixes and remaining acceptance](docs/release/2026-09-29-implementation-state.md)
- [Whole-system map](docs/architecture/system-map.md)
- [Architecture hub](docs/architecture/README.md)
- [Debugging playbook](docs/architecture/debugging-playbook.md)
- [All 20 priorities](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5872009447)
- [Master roadmap](https://github.com/GILBIC/spina-lending-app/issues/296)

The original Python/Tkinter desktop application and its separate local account system were retired at the owner's request. Their source and historical documentation remain recoverable through Git history. Existing business data and backups must be retained and reconciled through the supported authority; retirement does not migrate or erase those records.

## Main components

| Component | Location | Responsibility |
|---|---|---|
| Company portal | `spina_portal/` | Client, Collector, Employee and Management Web workspaces |
| Windows app | `spina_pc/` | Installs the same portal in Edge/Chrome app mode |
| Mobile app | `gilbic_mobile/` | Flutter presentation, secure sessions, device identity and scoped offline support |
| Backend | `gilbic_backend/` | Authentication integration, permissions, device approval and protected business workflows |
| Collection package | `spina_backend_mobile/` | Shared Payment/ADV/PASS contracts and idempotent PostgreSQL writes |
| Delivery | `.github/workflows/`, `ops/` | Hosted checks, protected maintenance and exact-source deployment |

Financial records, roles, permissions, approval, payroll and accounting results belong to the server. Interfaces may use different layouts but must preserve those outcomes. Accounting, HR/payroll and client-relationship permissions remain separate; Management retains sensitive approvals. Offline route snapshots are read-only, and financial writes require an authoritative online result.

Use the **SPINA cross-layer bug report** issue template for defects. Include safe record IDs and the exact build, without passwords, tokens, private documents or raw installation identifiers.

Passing automated checks establishes the tested source behavior. Company/provider configuration, permanent Android signing, real role/device acceptance, ongoing backup operations and representative performance require their own evidence in the current state. New Client Fund, renewal reserve and smart client capacity remain deferred.
