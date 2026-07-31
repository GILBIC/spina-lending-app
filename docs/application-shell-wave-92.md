# Application shell Wave 92

Wave 92 introduces `spina_app.features.application_shell` as the dedicated final installer for the desktop application shell.

## Ownership

The shell installer owns the installation sequence for:

1. account runtime and account-header callbacks
2. sidebar and role-aware navigation runtime
3. final desktop startup runtime

The historical `configure_account_header_dependencies` hook remains the desktop entry point, but it now performs only dependency injection and delegates to `install_application_shell`.

## Failure isolation

Each boundary is installed inside its own guarded section. A failed account installation does not prevent sidebar or startup installation, and the existing Wave 83, Wave 86, and Wave 89 suppressed-log keys are preserved.

## Preserved behavior

- account display names remain available to the extracted header presentation
- account switching and permission refresh remain owned by Wave 83
- sidebar rebuilding and role-aware navigation remain owned by Wave 86
- Tk root creation, startup cancellation, direct integration, and the main loop remain owned by Wave 89
- the final desktop entry point remains unchanged
- component installers remain idempotent

## Validation

The read-only Windows workflow checks out the exact pull-request commit with persisted credentials disabled. It compiles the desktop and shell modules, runs the focused Wave 92 order and failure-isolation regression, protected account/header tests, sidebar/navigation tests, startup tests through Wave 91, the permanent architecture map, and clean-tree validation.
