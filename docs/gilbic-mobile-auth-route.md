# Gilbic FastAPI authentication and collector route

This milestone replaces the development role picker with backend-controlled SPINA authentication and adds the first authenticated mobile data screen.

## Implemented flow

1. The user enters a username and password.
2. Gilbic sends the credentials to the configured FastAPI login endpoint.
3. FastAPI returns the authenticated account, role, permissions, and session token.
4. Gilbic maps the server role to a Client, Collector, Employee, or Management surface.
5. The authenticated session is stored through platform secure storage.
6. A Collector account may open the read-only assigned route.
7. The route request uses bearer authentication and remains filtered by FastAPI.

## Data and authority

Gilbic does not connect directly to PostgreSQL or Supabase PostgreSQL. The FastAPI backend remains responsible for:

- account status and credential checks
- role and permission enforcement
- collector assignment and route filtering
- SPINA loan, ADV, PASS, balance, and collection rules
- database transactions and audit logs

The mobile application only displays the response authorized for the current account.

## Configurable paths

The repository does not contain the existing `C:\SPINA_ONLINE\spina_backend` source, so this milestone does not hard-code an unverified legacy URL. The following Dart defines allow the live backend paths to be supplied without changing source code:

- `GILBIC_API_URL`
- `GILBIC_LOGIN_PATH`
- `GILBIC_LOGOUT_PATH`
- `GILBIC_COLLECTOR_ROUTE_PATH`

Default planned paths use the `/api/mobile/v1/` namespace. The parser also accepts the standard SPINA response envelope and the direct session fields previously used by the web portal.

## Security boundary

- Users cannot choose their own role in Gilbic.
- Tokens are stored with Android Keystore or Apple Keychain-backed secure storage.
- Collector route requests send bearer authentication.
- No database password is compiled into the mobile application.
- The route screen contains no payment, loan, renewal, reversal, or delete action.
- Server authorization remains required even when a screen is hidden in Flutter.

## Validation

The permanent Gilbic workflow checks out the exact same-repository pull-request head with persisted credentials disabled, resolves pinned dependencies, runs strict Flutter analysis, runs authentication and route tests, and requires a clean committed tree.

## Next boundary

The next mobile boundary is an encrypted SQLite route cache with last-synchronized status. Payment submission remains excluded until an idempotent FastAPI payment endpoint and conflict rules are verified.
