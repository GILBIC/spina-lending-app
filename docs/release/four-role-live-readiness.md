# Four-role live readiness

Date: 2026-09-03

## Verified infrastructure

- Hosted FastAPI `/health/ready` returns HTTP 200.
- Shared Supabase PostgreSQL database reports `database: ok`.
- Web, Windows and Android are configured to use the same backend authority.

## Current company account inventory

- Management: 1 assigned account.
- Collector: 2 assigned accounts.
- Client: 2 assigned accounts.
- Employee: 0 assigned accounts.
- Core users: 4 active accounts.
- Supabase Auth users: 4 confirmed, non-banned accounts.
- Registered devices: 52 active Android devices and 1 active desktop device.

## Release blockers

- A real Employee account has not been invited.
- Existing Collector and Client account records include test-labelled identities and are not acceptable as final company identities.
- Live sign-in and permission acceptance has not yet been completed for all four roles.
- Test-labelled accounts must be disabled or replaced only after real company accounts are working and linked correctly.

## Acceptance sequence

1. Management signs in through the hosted Spina portal.
2. Management invites one real Employee and one real Collector.
3. One real Client account is registered, approved and linked to the correct borrower record.
4. Each role signs in and confirms only its permitted workspace and actions.
5. Collector Android device approval, payment, receipt and Management visibility are verified.
6. Test-labelled identities are disabled after replacement accounts pass acceptance.

No passwords, API keys or connection strings are stored in this document.