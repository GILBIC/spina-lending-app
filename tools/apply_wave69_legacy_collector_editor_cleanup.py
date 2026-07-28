from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
WAVE43_TEST = ROOT / "tools" / "test_collector_dialog_presentation_wave_43.py"
WAVE69_TEST = ROOT / "tools" / "test_legacy_collector_editor_cleanup_wave_69.py"
WAVE69_WIDGET_TEST = ROOT / "tools" / "test_collector_editor_widget_smoke_wave_69.py"
TARGET = "_collector_editor_dialog"
EXPECTED_LINES = 136
EXPECTED_RAW_SHA256 = "93e983bbcaa6f77022abea2233f6d0f8159a2be6bfd6a23da52f0448d8f5969d"
EXPECTED_NORMALIZED_SHA256 = "3e8864685df23c9c8ac480be8ec411626a6b3680734209bf0a779c024c3b564a"
EXPECTED_SIGNATURE = "self, title='Collector', initial_name='', initial_areas=None, initial_notes=''"
ACTIVE_TARGET = "_spina_v27_collector_editor_dialog"
ACTIVE_BINDING = "App._collector_editor_dialog = _spina_v27_collector_editor_dialog"
CONFIGURE_CALL = "_configure_wave43_collector_dialog(globals())"


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def method_callers(app: ast.ClassDef) -> list[str]:
    callers: list[str] = []
    for method in app.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if method.name == TARGET:
            continue
        found = False
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == TARGET
                and isinstance(func.value, ast.Name)
                and func.value.id == "self"
            ):
                found = True
                break
        if found:
            callers.append(method.name)
    return sorted(callers)


def patch_wave43_test(text: str) -> str:
    old_constants = (
        "EXPECTED_OLD_APP_METHOD_LINES = 136\n"
        "EXPECTED_OLD_APP_METHOD_SHA256 = '3e8864685df23c9c8ac480be8ec411626a6b3680734209bf0a779c024c3b564a'\n"
    )
    if old_constants not in text:
        raise RuntimeError("Wave 43 legacy-method constants changed")
    text = text.replace(old_constants, "", 1)

    old_block = '''    app = next(n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    old_methods = [
        n for n in app.body
        if isinstance(n, ast.FunctionDef) and n.name == "_collector_editor_dialog"
    ]
    assert len(old_methods) == 1
    old = old_methods[0]
    dlines = desktop_text.splitlines(keepends=True)
    old_source = source_for(old, dlines)
    assert old.end_lineno - old.lineno + 1 == EXPECTED_OLD_APP_METHOD_LINES
    assert hashlib.sha256(normalized(old_source).encode("utf-8")).hexdigest() == EXPECTED_OLD_APP_METHOD_SHA256

    binding_line = desktop_text[:desktop_text.index(binding)].count("\\n") + 1
    assert old.end_lineno < binding_line
'''
    new_block = '''    app = next(n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    old_methods = [
        n for n in app.body
        if isinstance(n, ast.FunctionDef) and n.name == "_collector_editor_dialog"
    ]
    assert not old_methods, old_methods

    binding_line = desktop_text[:desktop_text.index(binding)].count("\\n") + 1
    main_index = desktop_text.rfind("\\ndef main(")
    assert main_index > 0
    main_line = desktop_text[:main_index].count("\\n") + 1
    assert binding_line < main_line
'''
    if old_block not in text:
        raise RuntimeError("Wave 43 legacy-method assertion block changed")
    return text.replace(old_block, new_block, 1)


def structural_test_source(callers: list[str]) -> str:
    return f'''from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "collector_dialog_presentation.py"
TARGET = {TARGET!r}
ACTIVE_TARGET = {ACTIVE_TARGET!r}
ACTIVE_BINDING = {ACTIVE_BINDING!r}
CONFIGURE_CALL = {CONFIGURE_CALL!r}
EXPECTED_CALLERS = {callers!r}


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(desktop_text, filename=str(DESKTOP))
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")

    legacy = [
        node for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    assert not legacy, legacy
    assert desktop_text.count(ACTIVE_BINDING) == 1
    assert CONFIGURE_CALL in desktop_text

    callers = []
    for method in app.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == TARGET
                and isinstance(func.value, ast.Name)
                and func.value.id == "self"
            ):
                callers.append(method.name)
                break
    assert sorted(callers) == EXPECTED_CALLERS, callers

    binding_index = desktop_text.index(ACTIVE_BINDING)
    main_index = desktop_text.rfind("\\ndef main(")
    assert binding_index < main_index

    spec = importlib.util.spec_from_file_location("wave69_collector_dialog", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(getattr(module, ACTIVE_TARGET))
    assert callable(module.configure_collector_dialog_dependencies)

    assert "Unified editor for Collector name + route areas + notes." not in desktop_text
    print("Wave 69 legacy collector editor cleanup regression passed:", EXPECTED_CALLERS)


if __name__ == "__main__":
    main()
'''


def widget_test_source() -> str:
    return '''from __future__ import annotations

import tkinter as tk
from pathlib import Path

from spina_app import collector_dialog_presentation as presentation

ROOT = Path(__file__).resolve().parents[1]


class FakeApp:
    def __init__(self, root):
        self.root = root


def colors(_self):
    return {
        "bg": "#f5f5f5",
        "panel": "#ffffff",
        "border": "#cccccc",
        "entry": "#ffffff",
        "fg": "#111111",
        "muted": "#555555",
        "blue": "#4477aa",
        "green": "#338855",
    }


def master_areas(_self):
    return ["North", "South", "East"]


def route_button(parent, text, command, kind="soft"):
    return tk.Button(parent, text=text, command=command)


def all_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from all_widgets(child)


def invoke_button(root, label):
    for widget in all_widgets(root):
        try:
            if str(widget.cget("text")) == label:
                widget.invoke()
                return
        except Exception:
            pass
    raise AssertionError(f"Button not found: {label}")


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    presentation.configure_collector_dialog_dependencies({
        "_spina_v27_route_colors": colors,
        "_spina_v27_get_route_master_areas": master_areas,
        "_spina_v27_route_button": route_button,
    })
    app = FakeApp(root)

    root.after(100, lambda: invoke_button(root, "Save Route"))
    saved = presentation._spina_v27_collector_editor_dialog(
        app,
        title="Collector",
        initial_name="Alice",
        initial_areas=["North", "South"],
        initial_notes="Priority route",
    )
    assert saved == {
        "name": "Alice",
        "areas": ["North", "South"],
        "notes": "Priority route",
    }, saved

    root.after(100, lambda: invoke_button(root, "Cancel"))
    cancelled = presentation._spina_v27_collector_editor_dialog(
        app,
        title="Collector",
        initial_name="Bob",
        initial_areas=["East"],
        initial_notes="",
    )
    assert cancelled is None

    root.destroy()
    print("Wave 69 collector editor real Tkinter smoke regression passed.")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    lines = desktop_text.splitlines(keepends=True)
    tree = ast.parse(desktop_text, filename=str(DESKTOP))
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    matches = [
        node for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one App.{TARGET}; found {len(matches)}")
    method = matches[0]
    source = "".join(lines[method.lineno - 1 : method.end_lineno])

    actual_lines = method.end_lineno - method.lineno + 1
    actual_raw = hashlib.sha256(source.encode("utf-8")).hexdigest()
    actual_normalized = hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()
    actual_signature = ast.unparse(method.args)
    if actual_lines != EXPECTED_LINES:
        raise RuntimeError(f"Line guard failed: {actual_lines}")
    if actual_raw != EXPECTED_RAW_SHA256:
        raise RuntimeError(f"Raw SHA guard failed: {actual_raw}")
    if actual_normalized != EXPECTED_NORMALIZED_SHA256:
        raise RuntimeError(f"Normalized SHA guard failed: {actual_normalized}")
    if actual_signature != EXPECTED_SIGNATURE:
        raise RuntimeError(f"Signature guard failed: {actual_signature}")
    if desktop_text.count(ACTIVE_BINDING) != 1:
        raise RuntimeError("Active Wave 43 binding missing or duplicated")
    if CONFIGURE_CALL not in desktop_text:
        raise RuntimeError("Wave 43 dependency configuration call missing")

    callers = method_callers(app)
    if not callers:
        raise RuntimeError("No active callers use self._collector_editor_dialog")

    start = method.lineno - 1
    end = method.end_lineno
    while end < len(lines) and not lines[end].strip():
        end += 1
    new_lines = lines[:start] + ["\n"] + lines[end:]
    new_text = "".join(new_lines)
    new_tree = ast.parse(new_text, filename=str(DESKTOP))
    new_app = next(node for node in new_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
        for node in new_app.body
    ):
        raise RuntimeError("Legacy method still present after removal")
    if new_text.count(ACTIVE_BINDING) != 1:
        raise RuntimeError("Active binding changed during removal")

    wave43_text = WAVE43_TEST.read_text(encoding="utf-8")
    patched_wave43 = patch_wave43_test(wave43_text)
    ast.parse(patched_wave43, filename=str(WAVE43_TEST))

    DESKTOP.write_text(new_text, encoding="utf-8")
    WAVE43_TEST.write_text(patched_wave43, encoding="utf-8")
    WAVE69_TEST.write_text(structural_test_source(callers), encoding="utf-8")
    WAVE69_WIDGET_TEST.write_text(widget_test_source(), encoding="utf-8")

    print(json.dumps({
        "removed": f"App.{TARGET}",
        "lines": EXPECTED_LINES,
        "raw_sha256": EXPECTED_RAW_SHA256,
        "normalized_sha256": EXPECTED_NORMALIZED_SHA256,
        "active_binding": ACTIVE_BINDING,
        "callers": callers,
    }, indent=2))


if __name__ == "__main__":
    main()
