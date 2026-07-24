from pathlib import Path

PATH = Path("docs/modularization-map.md")
text = PATH.read_text(encoding="utf-8")

replacements = [
    ("> **Tracked main state:** after merged PR #121  ", "> **Tracked main state:** after merged PR #122  "),
    ("| Functions extracted from the large desktop source | **71** |", "| Functions extracted from the large desktop source | **78** |"),
    ("| Feature-level tab modules | **2** |", "| Feature-level tab modules | **3** |"),
    ("| Accelerated modularization waves completed | **18** |", "| Accelerated modularization waves completed | **19** |"),
    ("| Latest completed extraction | **Wave 18 / PR #121** |", "| Latest completed extraction | **Wave 19 / PR #122** |"),
    ("| Next step | **Wave 19 feature inventory** |", "| Next step | **Wave 20 feature inventory** |"),
    ("    APP --> TABREPORTS[tabs/reports.py]\n", "    APP --> TABREPORTS[tabs/reports.py]\n    APP --> TABCLIENTS[tabs/clients.py]\n"),
    ("    TABREPORTS --> PAL\n", "    TABREPORTS --> PAL\n    TABCLIENTS --> UICTL\n    TABCLIENTS --> FMT\n"),
    ("| `spina_app/tabs/reports.py` | Modern Reports construction, controls, cards, table styling, selection status, and display refresh | 6 | 500 |\n", "| `spina_app/tabs/reports.py` | Modern Reports construction, controls, cards, table styling, selection status, and display refresh | 6 | 500 |\n| `spina_app/tabs/clients.py` | Modern Clients construction, controls, cards, selection/profile display, and card refresh | 7 | 387 |\n"),
    ("The Dashboard and Reports modules keep the original function names. The desktop entry module imports them back and supplies application-owned dependencies through late-bound bridges, avoiding circular imports while preserving existing App patching and callbacks.", "The Dashboard, Reports, and Clients modules keep the original function names. The desktop entry module imports them back and supplies application-owned dependencies through late-bound bridges, avoiding circular imports while preserving existing App patching and callbacks."),
    ("- `_spina_v22_update_report_cards` — PR #121\n\n## Modularization timeline", "- `_spina_v22_update_report_cards` — PR #121\n\n### `spina_app/tabs/clients.py`\n\n- `_spina_v23_button` — PR #122\n- `_spina_v23_card` — PR #122\n- `_spina_v23_selected_name_lt` — PR #122\n- `_spina_v23_refresh_client_profile` — PR #122\n- `_spina_v23_build_clients_tab` — PR #122\n- `_spina_v23_entry` — PR #122\n- `_spina_v23_update_client_cards` — PR #122\n\n## Modularization timeline"),
    ("| 18 | #121 inventory and working PR | #121 | `tabs/reports.py` | Modern Reports presentation group: 6 functions, 500 lines | ✅ Passed and merged |\n", "| 18 | #121 inventory and working PR | #121 | `tabs/reports.py` | Modern Reports presentation group: 6 functions, 500 lines | ✅ Passed and merged |\n| 19 | #122 inventory and working PR | #122 | `tabs/clients.py` | Modern Clients presentation group: 7 functions, 387 lines | ✅ Passed and merged |\n"),
    ("| 19 | Pending | Pending | Pending | Select through current-main feature inventory | ⬜ | ⬜ | ⬜ | Not started |", "| 19 | #122 | #122 | `tabs/clients.py` | 7 Clients feature functions; 387 lines moved | ✅ | ✅ | ✅ | Passed Windows smoke test and self-hosted audits |\n| 20 | Pending | Pending | Pending | Select through current-main feature inventory | ⬜ | ⬜ | ⬜ | Not started |"),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one occurrence of {old!r}; found {count}")
    text = text.replace(old, new, 1)

required = [
    "**78**",
    "**Wave 19 / PR #122**",
    "**Wave 20 feature inventory**",
    "`spina_app/tabs/clients.py` | Modern Clients",
    "_spina_v23_build_clients_tab` — PR #122",
    "| 19 | #122 inventory and working PR | #122 | `tabs/clients.py`",
    "| 20 | Pending |",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing updated marker: {marker}")

PATH.write_text(text, encoding="utf-8")
print("Wave 19 modularization map updated")
