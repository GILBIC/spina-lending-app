#!/usr/bin/env python3
"""Static regression check for the Reports notes drawer layout."""

from __future__ import annotations

import ast
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
TARGET = "_toggle_reports_notes_panel"


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)

    matches: list[tuple[ast.FunctionDef, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != TARGET:
            continue
        function_source = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        if 'self.report_notes_btn.configure(text="Hide Notes")' in function_source:
            matches.append((node, function_source))

    if len(matches) != 1:
        raise AssertionError(f"Expected one modern {TARGET}, found {len(matches)}")

    function_source = matches[0][1]
    box_pack = 'self.reports_notes_box.pack(side="bottom", fill="x", padx=18, pady=(0, 18))'
    sep_pack = 'self.reports_notes_sep.pack(side="bottom", fill="x", padx=18, pady=(0, 6))'

    if box_pack not in function_source:
        raise AssertionError("Reports notes box must reserve visible bottom space")
    if sep_pack not in function_source:
        raise AssertionError("Reports notes separator must reserve visible bottom space")
    if function_source.index(box_pack) > function_source.index(sep_pack):
        raise AssertionError("Pack the notes box before the separator so the separator stays above it")
    if 'self.reports_notes_box.pack_forget()' not in function_source:
        raise AssertionError("Hide behavior for the notes box was removed")
    if 'self.reports_notes_sep.pack_forget()' not in function_source:
        raise AssertionError("Hide behavior for the notes separator was removed")
    if 'self.report_notes_btn.configure(text="Hide Notes")' not in function_source:
        raise AssertionError("Visible-state button label was removed")


if __name__ == "__main__":
    main()
