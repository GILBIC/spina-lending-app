from pathlib import Path

PATH = Path("docs/modularization-map.md")
text = PATH.read_text(encoding="utf-8")

replacements = [
    ("> **Tracked main state:** after merged PR #118  ", "> **Tracked main state:** after merged PR #121  "),
    ("| Functions extracted from the large desktop source | **65** |", "| Functions extracted from the large desktop source | **71** |"),
    ("| Feature-level tab modules | **1** |", "| Feature-level tab modules | **2** |"),
    ("| Accelerated modularization waves completed | **17** |", "| Accelerated modularization waves completed | **18** |"),
    ("| Latest completed extraction | **Wave 17 / PR #118** |", "| Latest completed extraction | **Wave 18 / PR #121** |"),
    ("| Next step | **Wave 18 feature inventory** |", "| Next step | **Wave 19 feature inventory** |"),
    ("    APP --> TABDASH[tabs/dashboard.py]\n", "    APP --> TABDASH[tabs/dashboard.py]\n    APP --> TABREPORTS[tabs/reports.py]\n"),
    ("    TABDASH --> UIH\n", "    TABDASH --> UIH\n    TABREPORTS --> PAL\n"),
    ("| `spina_app/tabs/dashboard.py` | Legacy Dashboard construction, filtering, charts, table population, and refresh orchestration | 5 | 462 |\n", "| `spina_app/tabs/dashboard.py` | Legacy Dashboard construction, filtering, charts, table population, and refresh orchestration | 5 | 462 |\n| `spina_app/tabs/reports.py` | Modern Reports construction, controls, cards, table styling, selection status, and display refresh | 6 | 500 |\n"),
    ("The Dashboard module keeps the original function names. The desktop entry module imports them back and supplies database-row loading and logging through a late-bound bridge, avoiding circular imports while preserving existing App patching and callbacks.", "The Dashboard and Reports modules keep the original function names. The desktop entry module imports them back and supplies application-owned dependencies through late-bound bridges, avoiding circular imports while preserving existing App patching and callbacks."),
    ("- `_spina_v17_refresh_dashboard` — PR #118\n\n## Modularization timeline", "- `_spina_v17_refresh_dashboard` — PR #118\n\n### `spina_app/tabs/reports.py`\n\n- `_spina_v22_style_reports_tree` — PR #121\n- `_spina_v22_button` — PR #121\n- `_spina_v22_report_card` — PR #121\n- `_spina_v22_build_reports_tab` — PR #121\n- `_spina_v22_reports_selection_status` — PR #121\n- `_spina_v22_update_report_cards` — PR #121\n\n## Modularization timeline"),
    ("| 17 | #118 inventory and working PR | #118 | `tabs/dashboard.py` | Complete legacy Dashboard presentation/orchestration group: 5 functions, 462 lines | ✅ Passed and merged |\n", "| 17 | #118 inventory and working PR | #118 | `tabs/dashboard.py` | Complete legacy Dashboard presentation/orchestration group: 5 functions, 462 lines | ✅ Passed and merged |\n| 18 | #121 inventory and working PR | #121 | `tabs/reports.py` | Modern Reports presentation group: 6 functions, 500 lines | ✅ Passed and merged |\n"),
    ("| 18 | Pending | Pending | Pending | Select through current-main feature inventory | ⬜ | ⬜ | ⬜ | Not started |", "| 18 | #121 | #121 | `tabs/reports.py` | 6 Reports feature functions; 500 lines moved | ✅ | ✅ | ✅ | Passed Windows smoke test and self-hosted audits |\n| 19 | Pending | Pending | Pending | Select through current-main feature inventory | ⬜ | ⬜ | ⬜ | Not started |"),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one occurrence of {old!r}; found {count}")
    text = text.replace(old, new, 1)

required = [
    "**71**",
    "**Wave 18 / PR #121**",
    "**Wave 19 feature inventory**",
    "`spina_app/tabs/reports.py` | Modern Reports",
    "_spina_v22_build_reports_tab` — PR #121",
    "| 18 | #121 inventory and working PR | #121 | `tabs/reports.py`",
    "| 19 | Pending |",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing updated marker: {marker}")

PATH.write_text(text, encoding="utf-8")
print("Wave 18 modularization map updated")
