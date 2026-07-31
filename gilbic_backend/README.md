# Gilbic Backend

This is the new GitHub-first FastAPI backend for Gilbic.

Current foundation:

- FastAPI application factory
- liveness endpoint: `/health/live`
- API metadata endpoint: `/api/v1/meta`
- environment-based configuration
- isolated application tests

Planned order:

1. PostgreSQL or Supabase connection.
2. Accounts, roles, permissions, and devices.
3. Login and session authentication.
4. Collector route API.
5. Integrate the idempotent collection package already stored in `spina_backend_mobile/`.
6. Client, employee, and management APIs.
7. Accounting, billing, taxation, risk, and compliance APIs.

The old local FastAPI project is not required for this new foundation. Features can be migrated into this backend one by one after they are reviewed.
