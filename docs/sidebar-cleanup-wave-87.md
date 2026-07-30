# Sidebar cleanup Wave 87

Wave 86 established `spina_app.features.side_navigation.install_side_navigation_feature()` as the final owner of SPINA's sidebar lifecycle.

Wave 87 removes the runtime wrappers that are now dead:

- the v13 side-tabs-only block that rebound sidebar methods and wrapped startup, style, theme, and role access
- the later modern role-refresh wrapper that wrapped `apply_role_access` a second time

## Preserved ownership

The Wave 86 installer continues to own:

- dynamic visible-tab discovery
- hiding the main notebook tab row
- sidebar rebuild and selection refresh
- startup post-initialization
- theme and style refresh hooks
- role-change refresh hooks
- startup-cancellation propagation

After the cleanup, the installer selects the active methods through its fallback attributes instead of relying on legacy captured globals.

## Validation

The generated desktop cleanup compiled and passed Waves 87, 86, and 48 sidebar regressions, Wave 29 navigation behavior, account header and Tkinter smoke tests, startup cancellation, shutdown checks, Waves 83-85 account compatibility, the permanent architecture map, and generated-diff validation before it was committed to the pull-request branch.

The final workflow uses fail-fast command handling, and the startup-cancellation regression now verifies the modular Wave 86 wrapper instead of requiring the deleted v13 function.
