from __future__ import annotations

import ast
import pprint
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "spina_app" / "system_data_presentation.py"
EXACT_TEST = ROOT / "tools" / "test_system_data_presentation_wave_55.py"
WIDGET_TEST = ROOT / "tools" / "test_system_data_widget_smoke_wave_55.py"

NEW_SOURCE = """def _show_system_data_tab(self):
    try:
        tabs = set(self.nb.tabs())
        tab_id = str(self.tab_system_data)
        if tab_id not in tabs:
            self.nb.add(self.tab_system_data, text='Data')
        else:
            try:
                state = str(self.nb.tab(self.tab_system_data, 'state') or '').strip().lower()
            except Exception:
                state = ''
            if state == 'hidden':
                self.nb.add(self.tab_system_data, text='Data')
            else:
                self.nb.tab(self.tab_system_data, text='Data')
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_system_data_tab_show', 'suppressed exception excpass_system_data_tab_show', __spina_exc)
        pass
"""

NEW_META = {
    "lines": 18,
    "sha256": "7f68b43da86c941ed570d272da7f7c80c72c88aa7fb5deed17d0c7528a588927",
    "signature": "self",
    "calls": [
        "_log_suppressed_once",
        "lower",
        "self.nb.add",
        "self.nb.tab",
        "self.nb.tabs",
        "set",
        "str",
        "strip",
    ],
}


def replace_top_level_function(text: str, name: str, replacement: str) -> str:
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    lines[node.lineno - 1 : node.end_lineno] = [replacement]
    return "".join(lines)


def replace_literal_assignment(text: str, name: str, update) -> str:
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.Assign)
        and len(item.targets) == 1
        and isinstance(item.targets[0], ast.Name)
        and item.targets[0].id == name
    )
    value = ast.literal_eval(node.value)
    update(value)
    replacement = f"{name} = {pprint.pformat(value, width=140, sort_dicts=False)}\n"
    lines[node.lineno - 1 : node.end_lineno] = [replacement]
    return "".join(lines)


def replace_simple_assignment(text: str, name: str, replacement_value: str) -> str:
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.Assign)
        and len(item.targets) == 1
        and isinstance(item.targets[0], ast.Name)
        and item.targets[0].id == name
    )
    lines[node.lineno - 1 : node.end_lineno] = [f"{name} = {replacement_value}\n"]
    return "".join(lines)


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_text = replace_top_level_function(module_text, "_show_system_data_tab", NEW_SOURCE)
    module_text = replace_literal_assignment(
        module_text,
        "_SYSTEM_DATA_PRESENTATION_METADATA",
        lambda data: data.__setitem__("_show_system_data_tab", dict(NEW_META)),
    )
    module_text = replace_simple_assignment(
        module_text,
        "SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES",
        "183",
    )
    MODULE.write_text(module_text, encoding="utf-8")

    exact_text = EXACT_TEST.read_text(encoding="utf-8")
    exact_text = replace_literal_assignment(
        exact_text,
        "EXPECTED",
        lambda data: data.__setitem__("_show_system_data_tab", dict(NEW_META)),
    )
    exact_text = exact_text.replace(
        "assert module.SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES == 175",
        "assert module.SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES == 183",
        1,
    )
    EXACT_TEST.write_text(exact_text, encoding="utf-8")

    widget_text = WIDGET_TEST.read_text(encoding="utf-8")
    old = """        system_data._hide_system_data_tab(app)\n        root.update_idletasks()\n        assert str(app.tab_system_data) not in set(app.nb.tabs())\n        system_data._show_system_data_tab(app)\n        root.update_idletasks()\n        assert str(app.tab_system_data) in set(app.nb.tabs())\n        assert app.nb.tab(app.tab_system_data, \"text\") == \"Data\"\n"""
    new = """        system_data._hide_system_data_tab(app)\n        root.update_idletasks()\n        assert str(app.tab_system_data) in set(app.nb.tabs())\n        assert str(app.nb.tab(app.tab_system_data, \"state\")).lower() == \"hidden\"\n        system_data._show_system_data_tab(app)\n        root.update_idletasks()\n        assert str(app.tab_system_data) in set(app.nb.tabs())\n        assert str(app.nb.tab(app.tab_system_data, \"state\")).lower() != \"hidden\"\n        assert app.nb.tab(app.tab_system_data, \"text\") == \"Data\"\n"""
    if old not in widget_text:
        raise SystemExit("Widget hide/show block not found")
    WIDGET_TEST.write_text(widget_text.replace(old, new, 1), encoding="utf-8")

    print("Repaired System Data hidden-tab restoration and updated permanent regressions.")


if __name__ == "__main__":
    main()
