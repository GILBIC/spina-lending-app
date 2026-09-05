# Client Account Credential Lifecycle Design

## Purpose

Priority #3 replaces borrower self-registration with a SPINA-controlled Client account lifecycle. Client accounts are created only for an existing active, unlinked borrower record. SPINA generates the username and password, links the account to exactly one borrower, and keeps the backend authoritative for all permissions.

## Approved rules

- Public Client self-registration is disabled on Web/Mobile/API.
- Client account creation is a Management action and requires `account.manage`.
- The creator selects an existing active borrower whose `lending.clients.user_id` is still null.
- SPINA generates both username and password automatically; staff do not type either credential.
- The generated password is a normal account password. It stays valid until an authorized password-change action replaces it.
- SPINA returns the generated username/password only in the successful create/reset response and may deliver the credentials to the borrower by configured email. It must never persist a recoverable plaintext or reversibly encrypted copy of the password.
- Supabase Auth owns password hashing and verification.
- Client users cannot change or reset their own password.
- Collector users may change only their own password.
- Employee/Office Staff users may change their own password and may generate a new password for Client accounts only.
- Management users may change their own password and may generate a new password for any user account.
- Management mirroring/impersonation is a separate protected feature and must never depend on recovering a user's password. A mirrored action must preserve the real Management actor in audit history.
- Existing `core.client_registration_requests` rows are legacy data. New Client accounts do not create new self-registration requests, and the legacy table is not destructively dropped in this change.

## Username generation

Use the borrower's existing unique `client_code` as the stable source. Normalize it to lowercase ASCII letters/digits, replacing other runs with a single dot, trim leading/trailing dots, and prefix `spina.`. Example: `C-001` becomes `spina.c.001`. If the resulting username conflicts with an existing `core.users.username`, append `.2`, `.3`, and so on until an unused username is found. The selected username is stored normally in `core.users` and sent to the borrower.

## Password generation

Generate a cryptographically secure 16-character password using `secrets.SystemRandom`/`secrets.choice`. The generator must guarantee at least one uppercase letter, one lowercase letter, one digit, and one safe symbol from `@#$%`. Ambiguous characters (`O`, `0`, `I`, `l`, `1`) should be excluded where practical. The plaintext exists only in request-local memory, is passed once to Supabase Auth, may be passed once to the credential-email sender, and is returned once to the authorized caller. It must not be written to PostgreSQL, audit details, application logs, exception text, screenshots, or CI output.

## Backend creation flow

1. Authenticate the calling device and require `account.manage`.
2. Lock/read the selected borrower and require `status='active'` and `user_id is null`.
3. Generate the unique SPINA username and secure password.
4. Create the Supabase Auth user through the server-only admin API with the selected email, generated password, and confirmed email state.
5. In one PostgreSQL transaction, create an active `core.users` Client profile, assign only the `client` role, link `lending.clients.user_id`, and write an audit record containing no password.
6. If local persistence/linking fails after Supabase user creation, delete the newly created Supabase user as compensation.
7. After account/link success, attempt credential delivery through the configured sender. Email failure does not roll back a valid account because the caller still receives the one-time credentials and can deliver them manually. The response exposes `delivery_status` without exposing SMTP secrets.

## Password-change flow

- Self-change endpoint: authenticated non-Client users may change only their own password. Client role is rejected server-side even if a UI accidentally exposes the control.
- Client reset endpoint: Employee/Office Staff and Management may generate a new password for a Client account. Authorization uses a narrow `client.credential.manage` permission granted to `employee` and `management`; it is not granted to Collector or Client.
- Management reset endpoint: Management may generate a new password for any account using `account.manage`.
- A reset generates a fresh password; the previous password immediately becomes invalid in Supabase Auth. The plaintext new password is returned once and not retained.
- Every administrative password change writes an audit event with actor, target user, target role(s), and delivery status, never the password.

## Email delivery

Credential delivery is application email, not a Supabase invite flow. Use a generic SMTP adapter configured only from server-side environment variables. The current placeholders are:

- Sender display name: `SPINA Lending Company`
- Sender/login email: `spinalendingcompany@gmail.com`
- Website/domain label: `spina.com.ph`

For the Gmail placeholder, SMTP defaults may target `smtp.gmail.com:587` with STARTTLS, but host/port/user/password/from-name/from-address remain configuration so the provider can be replaced without business-logic changes. The SMTP password/app-password must never enter Git, API responses, logs, or audit details.

The Client credential message contains the SPINA brand, username, password, sign-in address label, and a short instruction to contact SPINA if access fails. It must not include loan balances, payment history, or other financial data.

## Authorization matrix

| Role | Change own password | Reset Client password | Reset other staff password | Create Client account | Mirror users |
| --- | --- | --- | --- | --- | --- |
| Client | No | No | No | No | No |
| Collector | Yes | No | No | No | No |
| Employee / Office Staff | Yes | Yes | No | No | No |
| Management | Yes | Yes | Yes | Yes | Yes, separate protected feature |

## Failure behavior

- Duplicate/linked borrower: `409`, no external or local side effect.
- Missing/inactive borrower: `404`/`409`, no account creation.
- Supabase Auth conflict: `409`, no local profile/link.
- Supabase Auth unavailable: `503`/`502`, no local profile/link.
- Local profile/link failure after Auth creation: compensate by deleting the created Auth user; return fail-closed error.
- Email delivery failure after successful account creation/reset: keep account/password valid, return delivery failure plus the one-time credential to the authorized caller, and never retry using a stored plaintext password.

## Testing and release constraints

- TDD is required for every behavior change.
- Keep the existing feature branch / draft PR #418; no production deployment, live database mutation, or live borrower credential email is authorized during implementation.
- Unit tests prove public registration is disabled, Client creation is Management-only, username/password are generated server-side, passwords never enter persistence/audit payloads, role-based password-change boundaries are fail-closed, and email failure does not destroy a valid account.
- Disposable PostgreSQL tests prove the borrower lock/link, Client-only role assignment, duplicate protection, audit event, and new `client.credential.manage` permission mapping.
- Portal and Flutter tests prove signed-out self-registration is absent and role surfaces expose only allowed controls.
- Exact-head SPINA CI must be green before merge is requested.
