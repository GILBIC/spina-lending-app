#!/usr/bin/env python3
"""Static regression check for the modern Reports Notes button."""

from __future__ import annotations

import ast
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
BUILDER = "_spina_v22_build_reports_tab"


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)

    builders = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == BUILDER
    ]
    if len(builders) != 1:
        raise AssertionError(f"Expected one {BUILDER}, found {len(builders)}")

    builder = builders[0]
    builder_source = "\n".join(lines[builder.lineno - 1 : builder.end_lineno])

    expected = "self.report_notes_btn.configure(command=self._open_note_dialog)"
    broken = "self.report_notes_btn.configure(command=_toggle_reports_notes_panel)"
    if builder_source.count(expected) != 1:
        raise AssertionError("Modern Reports Notes button must open the existing note editor dialog")
    if broken in builder_source:
        raise AssertionError("Modern Reports Notes button is still connected to the hidden inline drawer")

    dialog_defs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_open_note_dialog"
    ]
    if len(dialog_defs) != 1:
        raise AssertionError(f"Expected one _open_note_dialog method, found {len(dialog_defs)}")

    dialog_source = "\n".join(lines[dialog_defs[0].lineno - 1 : dialog_defs[0].end_lineno])
    required = (
        "self._get_selected_report_client()",
        "NoteEditorDialog(",
        "self._mode_filter()",
    )
    for text in required:
        if text not in dialog_source:
            raise AssertionError(f"Existing note dialog lost required behavior: {text}")


if __name__ == "__main__":
    main()
