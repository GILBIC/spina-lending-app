from __future__ import annotations

import ast
import hashlib
import json
import re
import textwrap
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/clients_tab_presentation.py")
TEST_EXACT = Path("tools/test_clients_tab_presentation_wave_55.py")
TEST_WIDGET = Path("tools/test_clients_tab_widget_smoke_wave_55.py")
PERMANENT_WORKFLOW = Path(".github/workflows/clients-tab-presentation-wave-55.yml")
TARGET = "_build_clients_tab"
EXPECTED_LINES = 156


def qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = qualified_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def main() -> None:
    src = MAIN.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    app = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App"), None)
    if app is None:
        raise SystemExit("App class not found")
    matches = [n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == TARGET]
    if len(matches) != 1:
        raise SystemExit(f"Expected one active App.{TARGET}, found {len(matches)}")
    method = matches[0]
    if method.end_lineno is None:
        raise SystemExit("Target has no end line")
    source_text = "".join(lines[method.lineno - 1:method.end_lineno])
    source_line_count = method.end_lineno - method.lineno + 1
    if source_line_count != EXPECTED_LINES:
        raise SystemExit(f"Refusing extraction: expected {EXPECTED_LINES} lines, found {source_line_count}")

    calls = sorted({qualified_name(n.func) for n in ast.walk(method) if isinstance(n, ast.Call) and qualified_name(n.func)})
    forbidden_suffixes = (
        ".execute", ".executemany", ".commit", ".rollback", ".write", ".save", ".unlink", ".remove",
        ".add_client", ".update_client", ".delete_client", ".add_or_update_transaction",
    )
    dangerous = [c for c in calls if c == "open" or c.endswith(forbidden_suffixes)]
    if dangerous:
        raise SystemExit(f"Refusing extraction: protected calls found: {dangerous}")

    digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    signature = ", ".join(a.arg for a in method.args.args)
    button_texts: list[str] = []
    label_texts: list[str] = []
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        name = qualified_name(node.func)
        text_value = None
        for kw in node.keywords:
            if kw.arg == "text" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                text_value = kw.value.value
                break
        if text_value is None:
            continue
        if name.endswith("Button") or "button" in name.lower():
            button_texts.append(text_value)
        elif name.endswith("Label") or name.endswith("LabelFrame"):
            label_texts.append(text_value)
    button_texts = list(dict.fromkeys(button_texts))
    label_texts = list(dict.fromkeys(label_texts))

    dedented = textwrap.dedent(source_text)
    metadata = {
        "lines": source_line_count,
        "sha256": digest,
        "signature": signature,
        "calls": calls,
        "button_texts": button_texts,
        "label_texts": label_texts,
    }
    protected = {
        "CLIENTS_TAB_PRESENTATION_TARGET", "CLIENTS_TAB_PRESENTATION_SOURCE_LINES",
        "CLIENTS_TAB_PRESENTATION_SOURCE_SHA256", "CLIENTS_TAB_PRESENTATION_SIGNATURE",
        "CLIENTS_TAB_PRESENTATION_CALLS", "CLIENTS_TAB_PRESENTATION_BUTTON_TEXTS",
        "CLIENTS_TAB_PRESENTATION_LABEL_TEXTS", "configure_clients_tab_presentation_dependencies",
        "_CLIENTS_TAB_PRESENTATION_DEPENDENCIES", "_PROTECTED_GLOBALS", TARGET,
        "__builtins__", "__cached__", "__doc__", "__file__", "__loader__", "__name__",
        "__package__", "__spec__",
    }
    module_text = (
        '"""Clients tab construction presentation extracted in Wave 55."""\n'
        "from __future__ import annotations\n\n"
        "_CLIENTS_TAB_PRESENTATION_DEPENDENCIES = {}\n"
        f"_PROTECTED_GLOBALS = {protected!r}\n\n"
        "def configure_clients_tab_presentation_dependencies(namespace):\n"
        "    _CLIENTS_TAB_PRESENTATION_DEPENDENCIES.clear()\n"
        "    _CLIENTS_TAB_PRESENTATION_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n"
        f"CLIENTS_TAB_PRESENTATION_TARGET = {TARGET!r}\n"
        f"CLIENTS_TAB_PRESENTATION_SOURCE_LINES = {source_line_count}\n"
        f"CLIENTS_TAB_PRESENTATION_SOURCE_SHA256 = {digest!r}\n"
        f"CLIENTS_TAB_PRESENTATION_SIGNATURE = {signature!r}\n"
        f"CLIENTS_TAB_PRESENTATION_CALLS = {calls!r}\n"
        f"CLIENTS_TAB_PRESENTATION_BUTTON_TEXTS = {button_texts!r}\n"
        f"CLIENTS_TAB_PRESENTATION_LABEL_TEXTS = {label_texts!r}\n\n"
        + dedented.rstrip() + "\n"
    )
    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(module_text, encoding="utf-8")

    del lines[method.lineno - 1:method.end_lineno]
    new_src = "".join(lines)
    marker = "# Wave 55: Clients tab construction presentation."
    if marker in new_src:
        raise SystemExit("Wave 55 binding already exists")
    binding = (
        "\n\n# Wave 55: Clients tab construction presentation.\n"
        "from spina_app.clients_tab_presentation import (\n"
        "    configure_clients_tab_presentation_dependencies as _configure_wave55_clients_tab_presentation,\n"
        "    _build_clients_tab as _wave55_build_clients_tab,\n"
        ")\n"
        "_configure_wave55_clients_tab_presentation(globals())\n"
        "App._build_clients_tab = _wave55_build_clients_tab\n"
    )
    main_matches = list(re.finditer(r"(?m)^def main\s*\(", new_src))
    if not main_matches:
        raise SystemExit("main() insertion point not found")
    pos = main_matches[-1].start()
    new_src = new_src[:pos] + binding + "\n" + new_src[pos:]
    MAIN.write_text(new_src, encoding="utf-8")

    exact_test = f'''from __future__ import annotations

import ast
import hashlib
from pathlib import Path

MAIN = Path("{MAIN.as_posix()}")
MODULE = Path("{MODULE.as_posix()}")
EXPECTED_LINES = {source_line_count}
EXPECTED_SHA256 = {digest!r}


def _function_source(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = src.splitlines(keepends=True)
    return "".join(lines[fn.lineno - 1:fn.end_lineno])


def main() -> None:
    module_source = _function_source(MODULE, "{TARGET}")
    assert len(module_source.splitlines()) == EXPECTED_LINES
    assert hashlib.sha256(module_source.encode("utf-8")).hexdigest() == EXPECTED_SHA256

    main_src = MAIN.read_text(encoding="utf-8")
    main_tree = ast.parse(main_src)
    app = next(n for n in main_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "{TARGET}" for n in app.body)
    assert main_src.count("# Wave 55: Clients tab construction presentation.") == 1
    assert main_src.count("App._build_clients_tab = _wave55_build_clients_tab") == 1
    assert main_src.count("configure_clients_tab_presentation_dependencies") == 1

    import spina_app.clients_tab_presentation as module
    assert module.CLIENTS_TAB_PRESENTATION_SOURCE_LINES == EXPECTED_LINES
    assert module.CLIENTS_TAB_PRESENTATION_SOURCE_SHA256 == EXPECTED_SHA256
    assert module.CLIENTS_TAB_PRESENTATION_SIGNATURE == "self"
    forbidden = (".execute", ".executemany", ".commit", ".rollback", ".write", ".unlink", ".remove")
    assert not [c for c in module.CLIENTS_TAB_PRESENTATION_CALLS if c == "open" or c.endswith(forbidden)]
    print("Wave 55 exact Clients-tab extraction regression passed")


if __name__ == "__main__":
    main()
'''
    TEST_EXACT.write_text(exact_test, encoding="utf-8")

    widget_test = '''from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import spina_app.clients_tab_presentation as presentation


class _Flexible:
    def __init__(self, owner, name):
        self.owner = owner
        self.name = name
    def __call__(self, *args, **kwargs):
        self.owner.calls.append((self.name, args, kwargs))
        parent = args[0] if args and isinstance(args[0], tk.Misc) else self.owner.tab_clients
        lower = self.name.lower()
        if "button" in lower:
            text = kwargs.get("text", "")
            command = kwargs.get("command")
            return ttk.Button(parent, text=text, command=command)
        if "tree" in lower:
            return ttk.Treeview(parent)
        return None
    def get(self, *args, **kwargs):
        return ""
    def set(self, *args, **kwargs):
        return None
    def __iter__(self):
        return iter(())
    def __bool__(self):
        return False


class DummyApp:
    def __init__(self, root):
        self.root = root
        self.tab_clients = ttk.Frame(root)
        self.tab_clients.pack(fill="both", expand=True)
        self.calls = []
    def __getattr__(self, name):
        value = _Flexible(self, name)
        setattr(self, name, value)
        return value


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        app = DummyApp(root)
        presentation.configure_clients_tab_presentation_dependencies({"tk": tk, "ttk": ttk})
        presentation._build_clients_tab(app)
        root.update_idletasks()

        widgets = list(_walk(app.tab_clients))
        assert len(widgets) >= 12, f"too few Clients widgets: {len(widgets)}"
        entries = [w for w in widgets if isinstance(w, (tk.Entry, ttk.Entry))]
        trees = [w for w in widgets if isinstance(w, ttk.Treeview)]
        buttons = [w for w in widgets if isinstance(w, (tk.Button, ttk.Button))]
        assert entries, "Clients tab has no search/filter entry"
        assert trees, "Clients tab has no client table"
        assert buttons, "Clients tab has no buttons"

        visible_texts = set()
        for widget in widgets:
            try:
                text = str(widget.cget("text") or "").strip()
            except Exception:
                text = ""
            if text:
                visible_texts.add(text)
        for text in presentation.CLIENTS_TAB_PRESENTATION_BUTTON_TEXTS:
            assert text in visible_texts, f"missing Clients button: {text}"
        for text in presentation.CLIENTS_TAB_PRESENTATION_LABEL_TEXTS:
            assert text in visible_texts, f"missing Clients label: {text}"

        command_buttons = []
        for button in buttons:
            try:
                if str(button.cget("command") or ""):
                    command_buttons.append(button)
            except Exception:
                pass
        assert command_buttons, "Clients buttons have no callbacks"
        assert hasattr(app, "clients_tree") or any(isinstance(w, ttk.Treeview) for w in widgets)
        print("Wave 55 real Tkinter Clients-tab construction test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
'''
    TEST_WIDGET.write_text(widget_test, encoding="utf-8")

    workflow = '''name: Clients tab presentation Wave 55

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
      - "spina_app/clients_tab_presentation.py"
      - "tools/test_clients_tab_presentation_wave_55.py"
      - "tools/test_clients_tab_widget_smoke_wave_55.py"
      - "architecture-map.json"
      - "docs/architecture/**"
      - ".github/workflows/clients-tab-presentation-wave-55.yml"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: clients-tab-presentation-wave-55-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  validate:
    if: github.event_name != 'pull_request' || github.head_ref == 'agent/high-volume-wave-55-clean'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 90
    steps:
      - name: Check out exact PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          fetch-depth: 0
          show-progress: false
      - name: Compile application, module, and tests
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app\\clients_tab_presentation.py
          python -m py_compile tools\\test_clients_tab_presentation_wave_55.py
          python -m py_compile tools\\test_clients_tab_widget_smoke_wave_55.py
          python -m compileall -q spina_app
      - name: Run exact Clients-tab extraction regression
        shell: cmd
        run: python -m tools.test_clients_tab_presentation_wave_55
      - name: Run real Tkinter Clients-tab construction test
        shell: cmd
        run: python -m tools.test_clients_tab_widget_smoke_wave_55
      - name: Run protected client and navigation regressions
        shell: cmd
        run: |
          python -m tools.test_clients_read_presentation_wave_30
          python -m tools.test_client_read_queries_wave_31
          python -m tools.test_client_form_presentation_wave_38
          python -m tools.test_navigation_and_databank_shell_wave_29
          python -m tools.test_side_navigation_presentation_wave_48
          python -m tools.test_side_navigation_widget_smoke_wave_48
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools\\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts\\wave-55-redundancy.json
          python tools\\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts\\wave-55-quality.json
      - name: Upload Wave 55 reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: clients-tab-presentation-wave-55-reports
          path: artifacts/wave-55-*.json
          if-no-files-found: warn
'''
    PERMANENT_WORKFLOW.write_text(workflow, encoding="utf-8")

    Path("artifacts/wave-55-extraction.json").parent.mkdir(exist_ok=True)
    Path("artifacts/wave-55-extraction.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
