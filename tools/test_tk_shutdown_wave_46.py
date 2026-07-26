from __future__ import annotations

import ast
import queue
import subprocess
import sys
import textwrap
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
METHODS = ("_prepare_tk_shutdown", "_destroy_root_safely", "_start_ui_queue_pump")
FORBIDDEN = ("invalid command name", "application has been destroyed", "ttk::ThemeChanged")


def load_methods():
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    found = {}
    for node in app.body:
        if isinstance(node, ast.FunctionDef) and node.name in METHODS:
            source = ast.get_source_segment(text, node)
            found[node.name] = source
    assert set(found) == set(METHODS), found.keys()
    namespace = {
        "queue": queue,
        "_log_exc": lambda *args, **kwargs: None,
        "_log_suppressed_once": lambda *args, **kwargs: None,
    }
    for name in METHODS:
        exec(textwrap.dedent(found[name]), namespace)
    return namespace


def child() -> None:
    import tkinter as tk
    from tkinter import ttk

    namespace = load_methods()

    class Harness:
        pass

    root = tk.Tk()
    root.withdraw()
    harness = Harness()
    harness.root = root
    harness._ui_queue = queue.Queue()
    harness._tk_shutdown_started = False
    harness._ui_queue_after_id = None
    for name in METHODS:
        setattr(harness, name, types.MethodType(namespace[name], harness))

    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    root.protocol("WM_DELETE_WINDOW", harness._destroy_root_safely)
    harness._start_ui_queue_pump()
    assert harness._ui_queue_after_id

    style = ttk.Style(root)
    themes = list(style.theme_names())

    def switch_theme_and_close():
        if len(themes) > 1:
            current = style.theme_use()
            target = next((name for name in themes if name != current), current)
            style.theme_use(target)
        harness._destroy_root_safely()

    root.after(1, switch_theme_and_close)
    root.mainloop()
    assert harness._tk_shutdown_started is True
    assert harness._ui_queue_after_id is None
    assert not errors, errors
    print("Wave 46 Tk shutdown child passed.")


def parent() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    assert text.count('root.protocol("WM_DELETE_WINDOW", self._destroy_root_safely)') == 1
    prepare_start = text.index("    def _prepare_tk_shutdown(self):")
    destroy_start = text.index("    def _destroy_root_safely(self):", prepare_start)
    prepare_source = text[prepare_start:destroy_start]
    assert prepare_source.count("self.root.after_cancel(after_id)") == 1
    assert text.count("self._ui_queue_after_id = self.root.after(50, _pump)") == 1
    assert text.index("self._tk_shutdown_started = False") < text.index("self._start_ui_queue_pump()")

    for _ in range(3):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        assert result.returncode == 0, combined
        lowered = combined.lower()
        for forbidden in FORBIDDEN:
            assert forbidden.lower() not in lowered, combined

    print("Wave 46 Tk shutdown regression passed.")


if __name__ == "__main__":
    if "--child" in sys.argv:
        child()
    else:
        parent()
