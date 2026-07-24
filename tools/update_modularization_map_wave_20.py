from pathlib import Path

PATH = Path("docs/modularization-map.md")
text = PATH.read_text(encoding="utf-8")

replacements = [
    ("> **Tracked main state:** after merged PR #122  ", "> **Tracked main state:** after merged PR #123  "),
    ("| Functions extracted from the large desktop source | **78** |", "| Functions extracted from the large desktop source | **85** |"),
    ("| Feature-level tab modules | **3** |", "| Feature-level tab modules | **4** |"),
    ("| Accelerated modularization waves completed | **19** |", "| Accelerated modularization waves completed | **20** |"),
    ("| Latest completed extraction | **Wave 19 / PR #122** |", "| Latest completed extraction | **Wave 20 / PR #123** |"),
    ("| Next step | **Wave 20 feature inventory** |", "| Next step | **Wave 21 feature inventory** |"),
    ("    APP --> TABCLIENTS[tabs/clients.py]\n", "    APP --> TABCLIENTS[tabs/clients.py]\n    APP --> TABCILOG[tabs/client_info_logs.py]\n"),
    ("    TABCLIENTS --> FMT\n", "    TABCLIENTS --> FMT\n    TABCILOG --> PAL\n    TABCILOG --> UIC\n    TABCILOG --> UICTL\n    TABCILOG --> UIH\n    TABCILOG --> DATE\n"),
    ("| `spina_app/tabs/clients.py` | Modern Clients construction, controls, cards, selection/profile display, and card refresh | 7 | 387 |\n", "| `spina_app/tabs/clients.py` | Modern Clients construction, controls, cards, selection/profile display, and card refresh | 7 | 387 |\n| `spina_app/tabs/client_info_logs.py` | Client Information Log construction, filters, charts, cards, table/detail rendering, and refresh orchestration | 7 | 516 |\n"),
    ("The Dashboard, Reports, and Clients modules keep the original function names.", "The Dashboard, Reports, Clients, and Client Information Log modules keep the original function names."),
    ("- `_spina_v23_update_client_cards` — PR #122\n\n## Modularization timeline", "- `_spina_v23_update_client_cards` — PR #122\n\n### `spina_app/tabs/client_info_logs.py`\n\n- `_spina_v24_cilog_action_color` — PR #123\n- `_spina_v24_cilog_stats` — PR #123\n- `_spina_v24_cilog_draw_charts` — PR #123\n- `_spina_v24_cilog_update_cards` — PR #123\n- `_spina_v24_build_client_info_logs_tab` — PR #123\n- `_spina_v24_render_client_info_logs` — PR #123\n- `_spina_v24_refresh_client_info_logs` — PR #123\n\n## Modularization timeline"),
    ("| 19 | #122 inventory and working PR | #122 | `tabs/clients.py` | Modern Clients presentation group: 7 functions, 387 lines | ✅ Passed and merged |\n", "| 19 | #122 inventory and working PR | #122 | `tabs/clients.py` | Modern Clients presentation group: 7 functions, 387 lines | ✅ Passed and merged |\n| 20 | #123 inventory and working PR | #123 | `tabs/client_info_logs.py` | Client Information Log presentation group: 7 functions, 516 lines | ✅ Passed and merged |\n"),
    ("| 20 | Pending | Pending | Pending | Select through current-main feature inventory | ⬜ | ⬜ | ⬜ | Not started |", "| 20 | #123 | #123 | `tabs/client_info_logs.py` | 7 CILog feature functions; 516 lines moved | ✅ | ✅ | ✅ | Passed Windows smoke test and self-hosted audits |\n| 21 | Pending | Pending | Pending | Select through current-main feature inventory | ⬜ | ⬜ | ⬜ | Not started |"),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one occurrence of {old!r}; found {count}")
    text = text.replace(old, new, 1)

required = [
    "**85**",
    "**Wave 20 / PR #123**",
    "**Wave 21 feature inventory**",
    "`spina_app/tabs/client_info_logs.py` | Client Information Log",
    "_spina_v24_build_client_info_logs_tab` — PR #123",
    "| 20 | #123 inventory and working PR | #123 | `tabs/client_info_logs.py`",
    "| 21 | Pending |",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing updated marker: {marker}")

PATH.write_text(text, encoding="utf-8")
print("Wave 20 modularization map updated")
