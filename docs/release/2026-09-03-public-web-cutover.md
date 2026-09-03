# Spina public Web cutover

Date: 2026-09-03

- The cross-platform Spina release was merged to `main` through PR #404.
- The permanent Vercel production address is the intended public Web entry point.
- The shared FastAPI and Supabase PostgreSQL backend remain authoritative.
- Four isolated acceptance identities were created for Client, Employee, Collector, and Management testing.
- Temporary account-creation routes and functions were disabled or removed immediately after use.
- No password, API key, database URL, or bootstrap token is recorded in this document.

Production acceptance requires the root page and `/health/ready` to return HTTP 200 before company users rely on the address.
