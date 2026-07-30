# Accounts Feature Boundary — Wave 83

## Purpose

Wave 83 establishes one final runtime owner for SPINA's account-based login integration without changing existing usernames, password hashes, first-login password-change rules, or role permissions.

## Architecture

- `spina_app/services/accounts.py`
  - supported access-profile normalization
  - stable default account display names
  - unique account-choice labels
  - selected-account label resolution
- `spina_app/features/accounts.py`
  - account metadata migration wrapper
  - account display and access-profile lookup
  - account switching controller
  - fallback role behavior
  - final idempotent `App` binding table
- `spina_app/login_dialog_presentation.py`
  - remains the active sign-in presentation
- `spina_app/account_header_presentation.py`
  - remains the active header presentation
  - its existing dependency configuration point now installs the Wave 83 boundary after the desktop file captures the original loader and header builder
- `spina_app/account_permission_presentation.py`
  - remains the permission-summary presentation rule

## Preserved behavior

- Existing account usernames and passwords are unchanged.
- Legacy salted SHA-256 password upgrades and PBKDF2 verification remain intact.
- Default accounts still require a password change on first login.
- `users.json` backup and recovery behavior remains intact.
- Admin, Encoder, Viewer, and System access behavior remains intact.
- The modern account login and account header presentations remain unchanged.
- Switching accounts still refreshes the header, navigation, and permission visibility.

## Runtime ownership

The Wave 46 header dependency call occurs after the desktop file has captured its original account loader and header builder. Wave 83 uses that point to install the final account methods on `App`, replacing the scattered late runtime bindings with one idempotent feature installer.

The older account method definitions remain in the desktop source as compatibility input for this transition. They are no longer the intended final runtime owner after the Wave 83 installer runs. A later cleanup wave can remove those dead definitions once Windows startup validation confirms the consolidated boundary.

## Validation

Wave 83 validates:

- pure account metadata rules
- metadata migration without credential replacement
- unique account labels
- account switching refresh behavior
- installer idempotence
- Wave 45 login presentation compatibility
- Wave 46 account-header compatibility
- Wave 47 permission-summary compatibility
- login-cancel and safe Tk shutdown behavior
