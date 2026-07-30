# Sidebar cleanup Wave 87 and validation Wave 88

Wave 86 established `spina_app.features.side_navigation.install_side_navigation_feature()` as the final owner of SPINA's sidebar lifecycle.

Wave 87 removed the runtime wrappers that became dead:

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

## Permanent validation Wave 88

Wave 88 removes the one-time cleanup generator and converts `.github/workflows/sidebar-cleanup-wave-87.yml` into permanent read-only validation.

The workflow now:

- uses `contents: read`
- checks out the exact PR commit with persisted credentials disabled
- never generates, commits, or pushes repository changes
- runs Waves 88, 87, 86, and 48 sidebar regressions
- runs navigation behavior, account header, startup cancellation, Tk shutdown, account Waves 83-85, and the architecture map
- requires a clean committed tree

`tools/test_sidebar_validation_wave_88.py` prevents the temporary generator, write permissions, or branch-writing commands from returning.
