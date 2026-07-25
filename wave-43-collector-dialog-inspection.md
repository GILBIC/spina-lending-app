# Wave 43 Collector Dialog Binding Inspection

Generated from the exact pull-request head.

## Candidate summaries

### `_spina_v27_collector_editor_dialog`

- Source: lines 37826–38175 (350 lines)
- Signature: `self, title='Collector', initial_name='', initial_areas=None, initial_notes=''`
- Normalized SHA-256: `acc8e500cd9e62435bd24d7e998c0dc3c6145e396437f22ca4ee8781c3bbe0f6`
- Nested callbacks: _panel, _assigned_keys, _refresh_lists, _clean_assigned_display, _add_selected, _remove_selected, _move_selected, _move_top, _move_bottom, _add_all_visible, _clear_assigned, _save, _cancel
- Global reads: _spina_v27_get_route_master_areas, _spina_v27_route_button, _spina_v27_route_colors, a, i, messagebox, re, tk, ttk
- Database calls: none
- Mutation/file calls: none
- SQL writes: none

### `_spina_v25_build_collectors_tab`

- Source: lines 37023–37368 (346 lines)
- Signature: `self`
- Normalized SHA-256: `c3da86caa9ae362f3e755bb47739d01ff48f97e4321b74ed044312dea1b56955`
- Nested callbacks: none
- Global reads: _log_exc, _on_search, _popup, _set_sort, _spina_v25_collector_button, _spina_v25_collector_card, _spina_v25_collector_colors, _spina_v25_style_collector_trees, _spina_v25_update_collector_cards, accent, i, messagebox, sub, title, tk, ttk, value, w
- Database calls: none
- Mutation/file calls: none
- SQL writes: none

### `_build_collectors_tab`

- Source: lines 16213–16559 (347 lines)
- Signature: `self`
- Normalized SHA-256: `47cb21c1ca5874f1a90978a3bf06c9085ac474838af6abf94d97ddaebf2fe32c`
- Nested callbacks: _set_sort, _popup, _on_search
- Global reads: tk, ttk
- Database calls: none
- Mutation/file calls: none
- SQL writes: none

### `_spina_v27_build_collectors_tab`

- Source: lines 37497–37789 (293 lines)
- Signature: `self`
- Normalized SHA-256: `5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb`
- Nested callbacks: none
- Global reads: _log_exc, _on_search, _popup, _select_status, _set_sort, _spina_v27_hidden_collector_widgets, _spina_v27_route_button, _spina_v27_route_card, _spina_v27_route_colors, _spina_v27_style_route_trees, _spina_v27_update_route_cards, accent, i, messagebox, sub, title, tk, ttk, value, w
- Database calls: none
- Mutation/file calls: none
- SQL writes: none

## Runtime binding assignments

- Line 37373: `App._build_collectors_tab = _spina_v25_build_collectors_tab`
- Line 38180: `App._build_collectors_tab = _spina_v27_build_collectors_tab`
- Line 38181: `App._collector_editor_dialog = _spina_v27_collector_editor_dialog`

## Candidate reference counts

- `_spina_v27_collector_editor_dialog`: 1 total references (1 loads, 0 stores); lines: 38181
- `_spina_v25_build_collectors_tab`: 1 total references (1 loads, 0 stores); lines: 37373
- `_build_collectors_tab`: 0 total references (0 loads, 0 stores); lines: 
- `_spina_v27_build_collectors_tab`: 1 total references (1 loads, 0 stores); lines: 38180

## Original App methods with matching names

- `App._collector_editor_dialog`: lines 9989–10124 (136 lines), SHA `3e8864685df23c9c8ac480be8ec411626a6b3680734209bf0a779c024c3b564a`
