from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "spina_app" / "databank_presentation.py"
STATIC_TEST = ROOT / "tools" / "test_databank_presentation_wave_49.py"
WIDGET_TEST = ROOT / "tools" / "test_databank_widget_smoke_wave_49.py"
WAVE53_WORKFLOW = ROOT / ".github" / "workflows" / "import-log-presentation-wave-53.yml"

TARGET = "_spina_v15_build_data_tab"
OLD_HASH = "06715b426fc112b66bf2cfca76ed844f7b5544276d6e9c867b6656e6b2c211ad"
OLD_BUTTON = "        # SPINA removed legacy Clients-tab action button statement"
NEW_BUTTON = "        ttk.Button(left_actions, text='Import Excel', style='Primary.TButton', command=self._import_from_excel_entry).pack(side='left', padx=3)"
OLD_CALL_FRAGMENT = "'self._mode_filter', 'self._month_label', 'self._update_data_toolbar'"
NEW_CALL_FRAGMENT = "'self._import_from_excel_entry', 'self._mode_filter', 'self._month_label', 'self._update_data_toolbar'"


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def source_for(text: str, name: str) -> str:
    tree = ast.parse(text)
    lines = text.splitlines()
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, (name, len(matches))
    node = matches[0]
    end = node.end_lineno or node.lineno
    return "\n".join(lines[node.lineno - 1:end])


def calls_for(text: str, name: str) -> list[str]:
    tree = ast.parse(text)
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1
    node = matches[0]

    def dotted(part: ast.AST) -> str:
        if isinstance(part, ast.Name):
            return part.id
        if isinstance(part, ast.Attribute):
            left = dotted(part.value)
            return f"{left}.{part.attr}" if left else part.attr
        return ""

    return sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})


def replace_exact(text: str, old: str, new: str, expected: int = 1) -> str:
    count = text.count(old)
    assert count == expected, (old, count, expected)
    return text.replace(old, new, expected)


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    before_source = source_for(module_text, TARGET)
    assert len(normalized(before_source).splitlines()) == 136
    assert source_hash(before_source) == OLD_HASH
    assert OLD_BUTTON in before_source
    assert "self._import_from_excel_entry" not in calls_for(module_text, TARGET)

    module_text = replace_exact(module_text, OLD_BUTTON, NEW_BUTTON)
    after_source = source_for(module_text, TARGET)
    new_hash = source_hash(after_source)
    new_calls = calls_for(module_text, TARGET)
    assert len(normalized(after_source).splitlines()) == 136
    assert new_hash != OLD_HASH
    assert "self._import_from_excel_entry" in new_calls

    module_text = replace_exact(module_text, OLD_HASH, new_hash)
    module_text = replace_exact(module_text, OLD_CALL_FRAGMENT, NEW_CALL_FRAGMENT)
    MODULE.write_text(module_text, encoding="utf-8")

    static_text = STATIC_TEST.read_text(encoding="utf-8")
    static_text = replace_exact(static_text, OLD_HASH, new_hash)
    static_text = replace_exact(static_text, OLD_CALL_FRAGMENT, NEW_CALL_FRAGMENT)
    STATIC_TEST.write_text(static_text, encoding="utf-8")

    widget_text = WIDGET_TEST.read_text(encoding="utf-8")
    widget_text = replace_exact(
        widget_text,
        "def widget_texts(widget):\n",
        "def find_button(widget, text):\n"
        "    for child in widget.winfo_children():\n"
        "        try:\n"
        "            if isinstance(child, ttk.Button) and str(child.cget('text')) == text:\n"
        "                return child\n"
        "        except Exception:\n"
        "            pass\n"
        "        found = find_button(child, text)\n"
        "        if found is not None:\n"
        "            return found\n"
        "    return None\n\n\n"
        "def widget_texts(widget):\n",
    )
    widget_text = replace_exact(
        widget_text,
        "        self.toolbar_count = 0\n",
        "        self.toolbar_count = 0\n        self.import_count = 0\n",
    )
    widget_text = replace_exact(
        widget_text,
        "    def open_databank_close_dialog(self):\n",
        "    def _import_from_excel_entry(self):\n"
        "        self.import_count += 1\n\n"
        "    def open_databank_close_dialog(self):\n",
    )
    widget_text = replace_exact(
        widget_text,
        "            \"Daily Close / View\",\n",
        "            \"Import Excel\",\n            \"Daily Close / View\",\n",
    )
    widget_text = replace_exact(
        widget_text,
        "        assert app.db_search_entry.winfo_exists()\n",
        "        assert app.db_search_entry.winfo_exists()\n"
        "        import_button = find_button(app.tab_data, 'Import Excel')\n"
        "        assert import_button is not None\n"
        "        import_button.invoke()\n"
        "        root.update_idletasks()\n"
        "        assert app.import_count == 1\n",
    )
    WIDGET_TEST.write_text(widget_text, encoding="utf-8")

    workflow_text = WAVE53_WORKFLOW.read_text(encoding="utf-8")
    workflow_text = replace_exact(
        workflow_text,
        '      - "spina_app/import_log_presentation.py"\n',
        '      - "spina_app/import_log_presentation.py"\n'
        '      - "spina_app/databank_presentation.py"\n'
        '      - "tools/test_databank_presentation_wave_49.py"\n'
        '      - "tools/test_databank_widget_smoke_wave_49.py"\n',
    )
    workflow_text = replace_exact(
        workflow_text,
        "          python -m py_compile spina_app\\import_log_presentation.py\n",
        "          python -m py_compile spina_app\\import_log_presentation.py\n"
        "          python -m py_compile spina_app\\databank_presentation.py\n"
        "          python -m py_compile tools\\test_databank_presentation_wave_49.py\n"
        "          python -m py_compile tools\\test_databank_widget_smoke_wave_49.py\n",
    )
    WAVE53_WORKFLOW.write_text(workflow_text, encoding="utf-8")

    # Final cross-file assertions before the repair is committed.
    final_module = MODULE.read_text(encoding="utf-8")
    final_static = STATIC_TEST.read_text(encoding="utf-8")
    final_widget = WIDGET_TEST.read_text(encoding="utf-8")
    assert source_hash(source_for(final_module, TARGET)) == new_hash
    assert final_module.count(NEW_BUTTON) == 1
    assert final_static.count(new_hash) == 1
    assert '"Import Excel"' in final_widget
    assert "import_button.invoke()" in final_widget

    print(f"Restored Data Bank Import Excel button; new source hash: {new_hash}")


if __name__ == "__main__":
    main()
