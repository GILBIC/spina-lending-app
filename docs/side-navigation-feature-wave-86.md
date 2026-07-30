# Side navigation feature Wave 86

Wave 86 establishes one final runtime owner for SPINA's left sidebar after the historical Wave 29 and Wave 48 bindings have loaded.

## Final ownership

`spina_app.features.side_navigation.install_side_navigation_feature()` now owns:

- dynamic visible-tab discovery
- side navigation rebuild and selected-state refresh
- hidden top notebook tabs
- sidebar refresh after application startup
- sidebar refresh after style and theme changes
- sidebar refresh after account-role changes

## Wrapper collapse

The installer selects the captured pre-sidebar implementations for:

- `App.__init__`
- `App._setup_style`
- `App._apply_ui_theme`
- `App.apply_role_access`

This prevents the final runtime from repeatedly rebuilding the sidebar through the older stacked wrappers. Startup cancellation remains outside all sidebar post-initialization error handling and therefore still propagates correctly.

## Integration

The existing late Wave 46 application-shell configuration hook installs Wave 86 after the legacy sidebar block has loaded. This makes Wave 86 the final runtime boundary without changing the large desktop entry file in this transition.

## Follow-up

A later cleanup wave can remove the now-dead v13 sidebar wrapper block and the redundant modern role-refresh wrapper from the desktop monolith.
