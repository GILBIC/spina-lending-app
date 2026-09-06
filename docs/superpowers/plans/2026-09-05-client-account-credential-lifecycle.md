# Client Account Credential Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Client self-registration with SPINA-generated Client credentials, restricted password administration, and professional credential-email delivery while preserving borrower-only authorization.

**Architecture:** FastAPI remains the only credential-management boundary. Supabase Auth owns password hashing and verification; PostgreSQL owns application roles, borrower linkage, permissions, and audit. Plaintext passwords exist only in request-local memory long enough to create/reset the Auth user, optionally send the credential email, and return the one-time credential to the authorized caller.

**Tech Stack:** FastAPI, Pydantic, Python `secrets`, `smtplib`, Supabase Auth Admin REST API, PostgreSQL/psycopg, Node portal tests, Flutter widget tests.

**Spec:** `docs/superpowers/specs/2026-09-05-client-account-credential-lifecycle-design.md`

## Global Constraints

- Public Client self-registration is disabled on Web/Mobile/API.
- New Client accounts attach only to an existing active unlinked borrower.
- SPINA generates username and password; no caller-supplied Client password or username.
- Never persist, log, audit, or expose later a recoverable copy of any generated password.
- Client cannot self-change/reset password.
- Collector may change only own password.
- Employee/Office Staff may change own password and reset Client passwords only.
- Management may change own password and reset any user password.
- `client.credential.manage` is granted only to Employee and Management.
- Existing legacy `core.client_registration_requests` data remains intact.
- No production deployment, live database mutation, or live borrower email during this plan.

---

### Task 1: Retire public Client self-registration and Mobile entry point

**Files:**
- Modify: `gilbic_backend/tests/test_client_account_creation_policy.py`
- Modify: `gilbic_backend/src/gilbic_backend/auth_api.py`
- Modify: `gilbic_mobile/lib/src/features/auth/login_page.dart`
- Modify: `gilbic_mobile/lib/src/app.dart`
- Test: `gilbic_mobile/test/client_account_creation_policy_test.dart`

**Interfaces:**
- Produces: public POST `/api/v1/auth/register` and `/api/mobile/v1/auth/register` return `410` with no side effects; signed-out Mobile shows only sign-in.

- [ ] Update the backend policy test so registration requires `410` and zero Auth/profile side effects.
- [ ] Run the exact backend policy test and record RED.
- [ ] Replace registration handling with a fail-closed retired endpoint that accepts no registration model before returning `410`.
- [ ] Run the backend policy test and record GREEN.
- [ ] Run the existing Flutter policy test and record RED for `Create client account`.
- [ ] Remove `ClientRegistrationPage` navigation and registration repository wiring from `LoginPage` / `GilbicApp` without deleting legacy review models yet.
- [ ] Run Flutter tests and record GREEN for the policy test.

### Task 2: Add deterministic username policy and secure generated passwords

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/client_credentials.py`
- Create: `gilbic_backend/tests/test_client_credentials.py`

**Interfaces:**
- Produces: `client_username_base(client_code: str) -> str`
- Produces: `generate_password(length: int = 16) -> str`

- [ ] Write RED unit tests for `C-001 -> spina.c.001`, punctuation collapse/trim, fallback normalization, 16-character password length, and required uppercase/lowercase/digit/`@#$%` classes.
- [ ] Run `pytest gilbic_backend/tests/test_client_credentials.py -q` and verify RED because the module/functions do not exist.
- [ ] Implement minimal pure helpers using `re`, `secrets.choice`, and a final secure shuffle; exclude ambiguous characters where practical.
- [ ] Run the unit test file and verify GREEN.

### Task 3: Extend Supabase Auth Admin for server-created users and password updates

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/auth_admin_client.py`
- Create: `gilbic_backend/tests/test_auth_admin_client_credentials.py`

**Interfaces:**
- Produces: `create_user(email: str, password: str, email_confirm: bool = True) -> UUID`
- Produces: `update_user_password(auth_user_id: UUID, password: str) -> None`

- [ ] Write RED HTTP-client tests proving `/auth/v1/admin/users` receives email/password/email_confirm and `/auth/v1/admin/users/{id}` receives only the new password.
- [ ] Verify RED because methods are absent.
- [ ] Implement the two server-only methods with existing headers/error mapping and without logging request bodies.
- [ ] Verify GREEN and retain existing invite/delete behavior.

### Task 4: Add professional credential-email adapter

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/config.py`
- Create: `gilbic_backend/src/gilbic_backend/credential_mailer.py`
- Create: `gilbic_backend/tests/test_credential_mailer.py`

**Interfaces:**
- Produces: `CredentialDeliveryResult(sent: bool, detail: str)`
- Produces: `SmtpCredentialMailer.send_client_credentials(email: str, full_name: str, username: str, password: str) -> CredentialDeliveryResult`
- Config defaults: sender name `SPINA Lending Company`, from/user `spinalendingcompany@gmail.com`, site label `spina.com.ph`, host `smtp.gmail.com`, port `587`; SMTP password defaults blank and is `repr=False`.

- [ ] Write RED tests for disabled/unconfigured delivery, branded subject/body, username/password inclusion, no financial data, STARTTLS/login/send behavior, and sanitized failure result.
- [ ] Verify RED because mailer/config fields do not exist.
- [ ] Implement the adapter with `EmailMessage` + `smtplib.SMTP`, STARTTLS, server-only config, and no secret/password logging.
- [ ] Verify GREEN.

### Task 5: Add Client credential-management permission migration

**Files:**
- Create: `gilbic_backend/sql/0111_add_client_credential_management.sql`
- Create: `gilbic_backend/tests/test_client_credential_management_migration.py`

**Interfaces:**
- Produces permission `client.credential.manage`.
- Maps permission to `employee` and `management` only.

- [ ] Write RED static migration test asserting permission creation, exact employee/management mappings, and absence of Client/Collector mappings.
- [ ] Verify RED because migration is absent.
- [ ] Add idempotent migration `0111_add_client_credential_management.sql`.
- [ ] Verify GREEN.

### Task 6: Create/link Client account atomically in PostgreSQL

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/management_repository.py`
- Create: `gilbic_backend/tests/test_client_account_creation_postgres.py`

**Interfaces:**
- Produces: `next_client_username(client_id: UUID) -> str` using locked borrower `client_code` + `core.users` collision checks.
- Produces: `create_client_account_profile(actor_user_id: UUID, auth_user_id: UUID, username: str, email: str, client_id: UUID) -> AccountAdminRecord`.
- Produces active Client-only account, borrower link, and password-free audit.

- [ ] Write RED disposable PostgreSQL tests for active/unlinked borrower requirement, generated username collision `.2`, active Client-only role assignment, borrower link, duplicate rejection, and audit details containing no password field/value.
- [ ] Verify RED because methods are absent.
- [ ] Implement repository locking/creation/audit transaction with fail-closed `AccountNotFound`/`AccountConflict` behavior.
- [ ] Verify GREEN in disposable PostgreSQL.

### Task 7: Replace invitation endpoint with generated Client credential creation

**Files:**
- Modify: `gilbic_backend/tests/test_client_account_creation_policy.py`
- Modify: `gilbic_backend/src/gilbic_backend/management_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/credential_mailer.py` only if dependency helper is required.

**Interfaces:**
- POST `/api/v1/management/client-accounts` body: `{client_id, email}` only.
- Response data: `{account, credentials: {username, password}, delivery: {sent, detail}}`.
- Requires `account.manage` and Management role.

- [ ] Replace old invite-style RED tests with caller-supplied username/password rejection and server-generated credential assertions.
- [ ] Add RED cases for no `account.manage`, non-Management actor, Supabase conflict/unavailable, local failure compensation, and email-failure non-rollback.
- [ ] Verify RED on exact policy tests.
- [ ] Implement Management endpoint: resolve generated username, generate password, create Supabase user, persist/link account, compensate Auth user on local failure, then attempt email delivery.
- [ ] Verify GREEN and ensure response/audit never exposes SMTP secrets.

### Task 8: Implement role-restricted password changes

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/auth_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/management_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/management_repository.py`
- Create: `gilbic_backend/tests/test_password_change_policy.py`

**Interfaces:**
- PATCH `/api/v1/auth/password` body `{password}` for authenticated non-Client self-change only.
- POST `/api/v1/management/accounts/{target_user_id}/password/reset` generates a new password server-side.
- Employee caller is allowed only when target has Client role and caller has `client.credential.manage`.
- Management caller with `account.manage` may reset any target.

- [ ] Write RED tests for Client self-change rejection, Collector self-change success, Employee self-change success, Management self-change success, Employee Client-reset success, Employee staff-reset rejection, Collector any-target reset rejection, and Management any-target reset success.
- [ ] Verify RED.
- [ ] Add repository account-target lookup needed for role checks and password-free audit metadata.
- [ ] Implement endpoints using Supabase Admin password update and generated password response for administrative reset.
- [ ] Verify GREEN.

### Task 9: Replace Management Web registration queue with Client account creation surface

**Files:**
- Create: `spina_portal/assets/client-account-admin.js`
- Modify: `spina_portal/assets/roles/management.js`
- Modify: `spina_portal/assets/roles.js`
- Modify: `spina_portal/tests/client-account-policy.test.mjs`
- Create: `spina_portal/tests/client-account-admin.test.mjs`

**Interfaces:**
- Management UI searches existing borrower candidates, accepts borrower + email only, calls POST `/api/v1/management/client-accounts`, and displays one-time generated username/password plus delivery status.

- [ ] Write RED module tests for request normalization, no username/password fields, `account.manage` gating, and one-time credentials rendering.
- [ ] Verify RED.
- [ ] Implement focused module and bind it into Management workspace; retire old active self-registration queue navigation while leaving legacy backend data readable.
- [ ] Verify portal GREEN.

### Task 10: Add Mobile password-control surfaces without restoring Client self-registration

**Files:**
- Modify existing role/account settings surfaces discovered in implementation; do not create parallel navigation.
- Create/modify focused Flutter tests for role controls.

**Interfaces:**
- Client: no change-password control.
- Collector/Employee/Management: own-password control.
- Employee/Management account administration: generated Client password reset where authorized.

- [ ] Write RED widget tests for role visibility first.
- [ ] Verify RED.
- [ ] Add minimal controls calling the protected backend endpoints.
- [ ] Verify GREEN and run full Flutter suite.

### Task 11: Exact-head verification and handoff

**Files:**
- No new behavior unless verification reveals a defect.

- [ ] Run full SPINA CI on exact feature head.
- [ ] Require Backend/quality/security GREEN.
- [ ] Require Financial/disposable PostgreSQL GREEN.
- [ ] Require Portal/Flutter/Android GREEN.
- [ ] Review PR diff for plaintext-password persistence/logging, permission broadening, stale self-registration entry points, and email secrets.
- [ ] Update PR #418, GitHub #296, Notion, and Create State with exact head/evidence.
- [ ] Keep PR draft and do not merge until explicit Management approval.
