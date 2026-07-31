# Startup runtime Wave 89

Wave 89 establishes `spina_app.features.startup_runtime` as the final owner of desktop application startup.

## Runtime ownership

The new runtime boundary owns:

- Tk root creation
- `App` construction
- startup-cancellation handling
- optional direct-integration attachment
- the Tk main loop

The installer enters through the existing late application-shell configuration hook after account and sidebar ownership are installed. It replaces the module-level `main` function without changing the historical compatibility blocks yet.

## Preserved behavior

- cancelled login destroys the root inside `App` and returns without entering the main loop
- unexpected startup errors still propagate
- direct-integration attachment failures are logged without preventing the desktop UI from opening
- late feature installers remain active because `App` and integration callbacks are resolved when `main()` runs
- startup installation is idempotent

## Validation

The read-only Windows workflow compiles the desktop application and startup modules, runs the focused Wave 89 runtime regression, protected login-cancellation and Tk-shutdown tests, account/header compatibility, Waves 86–88 sidebar and navigation checks, the permanent architecture map, and clean-tree validation.

## Follow-up

A later cleanup wave can remove the obsolete original `main()` implementation and placeholder `if __name__ == '__main__': pass` blocks after the final runtime owner is proven stable.
