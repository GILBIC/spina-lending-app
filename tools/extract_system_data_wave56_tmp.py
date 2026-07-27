from __future__ import annotations

import ast
import codecs
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "system_data_presentation.py"
EXACT_TEST = ROOT / "tools" / "test_system_data_presentation_wave_56.py"
WIDGET_TEST = ROOT / "tools" / "test_system_data_widget_smoke_wave_56.py"
REPORT = ROOT / "artifacts" / "wave-56-system-data-extraction.json"
TARGET_CLASS = "App"
TARGET_METHOD = "_build_system_data_tab"
EXPECTED_LINES = 46
EXPECTED_SHA256 = "b4d8ff8e73daca66a7aa4d6d5e8e08fe5d91648f04c7a2e485fb0677add79f3d"
EXPECTED_SIGNATURE = "self"
EXPECTED_CALLS = [
    "_dt.now", "_log_suppressed_once", "controls.columnconfigure", "controls.grid",
    "grid", "outer.columnconfigure", "outer.rowconfigure", "range",
    "self._get_databank_focus_date", "self._system_data_refresh_summary", "strftime",
    "summary.columnconfigure", "summary.grid", "summary.rowconfigure",
    "title.columnconfigure", "title.grid", "tk.StringVar", "ttk.Button", "ttk.Entry",
    "ttk.Frame", "ttk.Label", "ttk.LabelFrame",
]
FORBIDDEN_FRAGMENTS = (
    ".execute", ".executemany", ".commit", ".rollback", "insert", "delete_transaction",
    "update_transaction", "set_transaction", "add_transaction", "close_day", "reopen_day",
    "backup", "restore", "password", "pg_dump", "unlink", "write_text", "write_bytes",
)


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def find_target(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == TARGET_METHOD:
                    return child
    raise SystemExit(f"Missing {TARGET_CLASS}.{TARGET_METHOD}")


def static_text(call: ast.Call) -> str | None:
    for kw in call.keywords:
        if kw.arg == "text" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def command_name(value: ast.AST) -> str | None:
    direct = dotted(value)
    if direct.startswith("self."):
        return direct.split(".", 1)[1]
    for node in ast.walk(value):
        if isinstance(node, ast.Attribute):
            name = dotted(node)
            if name.startswith("self."):
                return name.split(".", 1)[1]
    return None


def render_module(dedented: str, metadata: dict[str, object]) -> str:
    protected = {
        "__name__", "__file__", "__package__", "__loader__", "__spec__", "__builtins__",
        "__cached__", "__doc__", "_SYSTEM_DATA_PRESENTATION_DEPENDENCIES", "_PROTECTED_GLOBALS",
        "configure_system_data_presentation_dependencies", TARGET_METHOD,
    }
    protected.update(metadata)
    lines = [
        '"""System Data tab construction presentation extracted in Wave 56."""',
        "from __future__ import annotations",
        "",
        "_SYSTEM_DATA_PRESENTATION_DEPENDENCIES = {}",
        f"_PROTECTED_GLOBALS = {protected!r}",
        "",
        "def configure_system_data_presentation_dependencies(namespace):",
        "    _SYSTEM_DATA_PRESENTATION_DEPENDENCIES.clear()",
        "    _SYSTEM_DATA_PRESENTATION_DEPENDENCIES.update(namespace)",
        "    for name, value in namespace.items():",
        "        if name not in _PROTECTED_GLOBALS:",
        "            globals()[name] = value",
        "",
    ]
    for name, value in metadata.items():
        lines.append(f"{name} = {value!r}")
    lines.extend(["", dedented.rstrip(), ""])
    return "\n".join(lines)


def render_exact_test(metadata: dict[str, object]) -> str:
    return f'''"""Exact-source regression for Wave 56 System Data presentation."""
from __future__ import annotations

import ast
import hashlib
import inspect
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


def main() -> None:
    import spina_app.system_data_presentation as module

    assert module.SYSTEM_DATA_PRESENTATION_TARGET == {TARGET_METHOD!r}
    assert module.SYSTEM_DATA_PRESENTATION_SOURCE_LINES == {EXPECTED_LINES}
    assert module.SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 == {EXPECTED_SHA256!r}
    assert module.SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256 == {metadata['SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256']!r}
    assert module.SYSTEM_DATA_PRESENTATION_SIGNATURE == {EXPECTED_SIGNATURE!r}
    assert module.SYSTEM_DATA_PRESENTATION_CALLS == {EXPECTED_CALLS!r}

    module_source = inspect.getsource(module._build_system_data_tab)
    assert len(module_source.splitlines()) == {EXPECTED_LINES}
    assert hashlib.sha256(module_source.encode("utf-8")).hexdigest() == module.SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256

    app_text = APP.read_text(encoding="utf-8-sig")
    tree = ast.parse(app_text, filename=str(APP))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            assert not any(isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == {TARGET_METHOD!r} for child in node.body)

    assert app_text.count("_configure_wave56_system_data_presentation(globals())") == 1
    assert app_text.count("App._build_system_data_tab = _wave56_build_system_data_tab") == 1
    lowered = "\n".join(module.SYSTEM_DATA_PRESENTATION_CALLS).lower()
    assert not [fragment for fragment in {FORBIDDEN_FRAGMENTS!r} if fragment in lowered]
    print("Wave 56 exact System Data extraction regression passed")


if __name__ == "__main__":
    main()
'''


def render_widget_test(metadata: dict[str, object]) -> str:
    return f'''"""Real Tkinter smoke test for Wave 56 System Data presentation."""
from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk

import spina_app.system_data_presentation as module


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.tab_system_data = ttk.Frame(root)
        self.tab_system_data.grid(row=0, column=0, sticky="nsew")
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            def stub(*args, **kwargs):
                self.calls.append(name)
                if name == "_get_databank_focus_date":
                    return "2026-07-27"
                return None
            return stub
        raise AttributeError(name)


def main() -> None:
    module.configure_system_data_presentation_dependencies({{
        "tk": tk,
        "ttk": ttk,
        "_dt": _dt,
        "_log_suppressed_once": lambda *args, **kwargs: None,
    }})
    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp(root)
        module._build_system_data_tab(app)
        root.update_idletasks()
        widgets = list(walk(app.tab_system_data))
        texts = {{str(w.cget("text")) for w in widgets if "text" in w.keys()}}
        assert set(module.SYSTEM_DATA_PRESENTATION_BUTTON_TEXTS) <= texts
        assert set(module.SYSTEM_DATA_PRESENTATION_LABEL_TEXTS) <= texts
        for attr in module.SYSTEM_DATA_PRESENTATION_SELF_ATTRIBUTES:
            assert hasattr(app, attr), attr
        for text, callback in module.SYSTEM_DATA_PRESENTATION_BUTTON_CALLBACKS:
            button = next(w for w in widgets if isinstance(w, ttk.Button) and str(w.cget("text")) == text)
            app.calls.clear()
            button.invoke()
            assert callback in app.calls, (text, callback, app.calls)
        print("Wave 56 real Tkinter System Data construction test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
'''


def main() -> None:
    raw = APP.read_bytes()
    had_bom = raw.startswith(codecs.BOM_UTF8)
    text = raw.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    target = find_target(tree)
    if target.end_lineno is None:
        raise SystemExit("Target end line missing")
    source = "".join(lines[target.lineno - 1 : target.end_lineno])
    if target.end_lineno - target.lineno + 1 != EXPECTED_LINES:
        raise SystemExit("Wave 56 line boundary changed")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Wave 56 source hash changed: {digest}")
    signature = ast.unparse(target.args)
    if signature != EXPECTED_SIGNATURE:
        raise SystemExit(f"Wave 56 signature changed: {signature}")
    calls = sorted({dotted(n.func) for n in ast.walk(target) if isinstance(n, ast.Call) and dotted(n.func)})
    if calls != EXPECTED_CALLS:
        raise SystemExit(f"Wave 56 call set changed: {calls}")
    lowered = "\n".join(calls).lower()
    hits = [fragment for fragment in FORBIDDEN_FRAGMENTS if fragment in lowered]
    if hits:
        raise SystemExit(f"Protected calls detected: {hits}")

    self_attrs = sorted({
        n.attr for n in ast.walk(target)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" and isinstance(n.ctx, ast.Store)
    })
    button_texts: list[str] = []
    label_texts: list[str] = []
    button_callbacks: list[tuple[str, str]] = []
    for node in ast.walk(target):
        if not isinstance(node, ast.Call):
            continue
        func = dotted(node.func)
        text_value = static_text(node)
        if func.endswith("Button") and text_value:
            button_texts.append(text_value)
            for kw in node.keywords:
                if kw.arg == "command":
                    callback = command_name(kw.value)
                    if callback:
                        button_callbacks.append((text_value, callback))
        elif (func.endswith("Label") or func.endswith("LabelFrame")) and text_value:
            label_texts.append(text_value)

    dedented = textwrap.dedent(source)
    dedented_sha = hashlib.sha256(dedented.encode("utf-8")).hexdigest()
    metadata = {
        "SYSTEM_DATA_PRESENTATION_TARGET": TARGET_METHOD,
        "SYSTEM_DATA_PRESENTATION_SOURCE_LINES": EXPECTED_LINES,
        "SYSTEM_DATA_PRESENTATION_SOURCE_SHA256": EXPECTED_SHA256,
        "SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256": dedented_sha,
        "SYSTEM_DATA_PRESENTATION_SIGNATURE": EXPECTED_SIGNATURE,
        "SYSTEM_DATA_PRESENTATION_CALLS": calls,
        "SYSTEM_DATA_PRESENTATION_SELF_ATTRIBUTES": self_attrs,
        "SYSTEM_DATA_PRESENTATION_BUTTON_TEXTS": sorted(set(button_texts)),
        "SYSTEM_DATA_PRESENTATION_LABEL_TEXTS": sorted(set(label_texts)),
        "SYSTEM_DATA_PRESENTATION_BUTTON_CALLBACKS": button_callbacks,
    }
    MODULE.write_text(render_module(dedented, metadata), encoding="utf-8")
    EXACT_TEST.write_text(render_exact_test(metadata), encoding="utf-8")
    WIDGET_TEST.write_text(render_widget_test(metadata), encoding="utf-8")

    new_text = "".join(lines[: target.lineno - 1] + lines[target.end_lineno :])
    marker = "\ndef main():"
    if marker not in new_text:
        raise SystemExit("Wave 56 startup marker missing")
    if "_configure_wave56_system_data_presentation" in new_text:
        raise SystemExit("Wave 56 binding already exists")
    binding = '''\n\n# Wave 56: System Data tab construction presentation.\nfrom spina_app.system_data_presentation import (\n    configure_system_data_presentation_dependencies as _configure_wave56_system_data_presentation,\n    _build_system_data_tab as _wave56_build_system_data_tab,\n)\n_configure_wave56_system_data_presentation(globals())\nApp._build_system_data_tab = _wave56_build_system_data_tab\n'''
    new_text = new_text.replace(marker, binding + marker, 1)
    encoded = new_text.encode("utf-8")
    if had_bom:
        encoded = codecs.BOM_UTF8 + encoded
    APP.write_bytes(encoded)

    report = {
        "target": f"{TARGET_CLASS}.{TARGET_METHOD}",
        "lines": EXPECTED_LINES,
        "sha256": EXPECTED_SHA256,
        "dedented_sha256": dedented_sha,
        "signature": EXPECTED_SIGNATURE,
        "calls": calls,
        "self_attributes": self_attrs,
        "button_texts": sorted(set(button_texts)),
        "label_texts": sorted(set(label_texts)),
        "button_callbacks": button_callbacks,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
