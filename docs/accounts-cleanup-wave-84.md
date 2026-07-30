# Accounts architecture Waves 84-85

Wave 84 removed account runtime definitions that became dead after Wave 83 established `spina_app.features.accounts.install_accounts_feature()` as the final owner.

## Removed from the desktop monolith

- legacy `App._prompt_login`
- legacy `App._prompt_user_role`
- duplicate `App._refresh_user_header`
- duplicate `App.switch_account`
- v32 account naming, choice, metadata-migration, switching, and role-fallback helpers
- direct v32 `App` method rebinding

## Preserved

- password hashing and legacy hash upgrade
- forced first-login password change
- `users.json` backup and recovery
- account metadata migration
- modern login and header presentation
- role-based access application
- startup cancellation and Tk shutdown behavior

The remaining desktop integration is a compact Wave 46 configuration call. That call installs the Wave 83 accounts boundary and supplies the login presentation with its theme and button dependencies.

## Wave 84 validation

The cleanup compiled and passed the Wave 84 architecture regression, Wave 83 account regression, protected Waves 45-47 login/header/permission tests, Tkinter smoke tests, startup cancellation, Tk shutdown, and architecture-map validation before it was merged.

## Wave 85 permanent validation

Wave 85 removes the one-time cleanup generator and templates. The retained workflow is read-only and:

- checks out the exact pull-request commit with persisted credentials disabled
- compiles the desktop application and account modules
- runs the permanent Waves 83-85 account architecture regressions
- runs protected Waves 45-47 login, header, permission, startup, and shutdown tests
- validates the permanent architecture map
- requires a clean committed working tree

The Wave 85 guard fails if temporary cleanup tooling returns, the workflow regains write permission, or commit/push commands are added to the account validation workflow.
