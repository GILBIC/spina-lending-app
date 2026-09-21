# Staff password controls on Web

The Account section in the Collector, Employee and Management workspaces uses the existing FastAPI credential endpoints. The backend remains authoritative for permissions, password changes, audit events and configured credential email delivery.

## Who can do what

| Signed-in staff | Own password | Reset Client password | Reset staff password |
| --- | --- | --- | --- |
| Collector | Yes | No | No |
| Employee | Yes | With client.credential.manage | No |
| Management | Yes | With client.credential.manage or account.manage | With account.manage |

Client membership does not expose these staff controls. The website does not add Client self-registration or borrower self-service password resets.

## Change your password

Open Account, enter the new password twice, then submit while connected. Password characters, including leading or trailing spaces, are preserved. A successful response confirms the change; a rejected or interrupted request must not be described as successful.

## Reset an account

Use the account search, select the exact returned identity and review the confirmation before generating a replacement password. Employee searches use the Client-only endpoint. Management with account.manage can search the broader account list.

The backend generates the password. It is returned only in the reset response and shown masked until staff deliberately reveal it. Delivery status describes whether the existing server-side email adapter sent credentials; failed delivery does not undo a completed reset. Dismiss the handoff when finished. Passwords are not stored in browser storage, URLs, logs or an offline queue.

If the response reports incomplete final audit recording, the password has still changed. Keep the returned handoff and follow up on the audit warning; do not repeat the reset to repair the audit.

## Lost connection and navigation

A password mutation is never automatically retried. When a result is unknown, the old password may already have been replaced and the controls remain locked. Check with the account holder or check the credential email before using the workspace Refresh button. After refreshing, look up the account again and deliberately confirm another reset only if needed. Looking up the account does not recover or establish the previous attempt's generated password.

Logout, access rejection, workspace replacement and disposal clear entered and returned secrets. Late responses cannot put credentials back into an abandoned workspace. Staff must remain connected to submit changes.

## Verification scope

Portal tests exercise role/permission visibility, exact request contracts, confirmation, malformed responses, duplicate submission, uncertain outcomes and lifecycle cleanup. Workspace tests use the real role mounts; synthetic browser acceptance checks desktop and narrow layouts. The existing backend password policy and audit tests provide compatibility coverage.

These checks do not change real account passwords, send real credential email or establish production deployment. No database migration or Auth-provider change is required. The service-worker shell version is updated so the shared credential module is available after a PWA refresh.
