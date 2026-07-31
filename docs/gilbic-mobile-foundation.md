# Gilbic mobile foundation

Gilbic is the role-based mobile companion to SPINA. The mobile application does
not connect directly to PostgreSQL. It communicates with the existing FastAPI
backend, which remains responsible for authentication, permissions, loan rules,
payment validation, accounting entries, audit logs, and database access.

## Initial role surfaces

- Client: loans, payments, receipts, renewal, and support
- Collector: daily route, payment entry, offline synchronization, and end-of-day
- Employee: attendance, payroll, tasks, and requests
- Management: loan management, operations, accounting, billing and taxation,
  risk and compliance, and administration

## Data ownership

- PostgreSQL or Supabase PostgreSQL stores official records.
- FastAPI is the only trusted business-rule and database boundary.
- The mobile local database stores downloaded routes and pending offline work.
- The server remains the official owner of balances, payments, receipts, and
  accounting entries.

## Foundation boundaries

`SessionStore` allows the preview memory store to be replaced with secure mobile
storage. `LocalDatabase` allows the preview memory queue to be replaced with an
encrypted SQLite implementation. `ApiConfig` allows development, staging, and
production API addresses without committing secrets.

## Delivery sequence

1. foundation and role dashboards
2. real FastAPI authentication
3. read-only collector route
4. encrypted offline route cache
5. idempotent payment synchronization
6. client loan and payment timeline
7. management approvals and reporting
