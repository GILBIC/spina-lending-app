from __future__ import annotations

import ast
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TEST = ROOT / "tools/test_tk_shutdown_wave_46.py"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    if "def _prepare_tk_shutdown(self):" in text:
        raise AssertionError("Wave 46 Tk shutdown repair is already present")

    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    tree = ast.parse(text)

    app_classes = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    ]
    assert len(app_classes) == 1, len(app_classes)
    app = app_classes[0]

    init_methods = [
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    ]
    pump_methods = [
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == "_start_ui_queue_pump"
    ]
    assert len(init_methods) == 1, len(init_methods)
    assert len(pump_methods) == 1, len(pump_methods)
    init = init_methods[0]
    pump = pump_methods[0]

    pump_calls = [
        node for node in ast.walk(init)
        if isinstance(node, ast.Call) and dotted(node.func) == "self._start_ui_queue_pump"
    ]
    root_destroy_calls = [
        node for node in ast.walk(init)
        if isinstance(node, ast.Call) and dotted(node.func) == "root.destroy"
    ]
    assert len(pump_calls) == 1, len(pump_calls)
    assert len(root_destroy_calls) == 1, len(root_destroy_calls)

    pump_call = pump_calls[0]
    destroy_call = root_destroy_calls[0]
    assert lines[pump_call.lineno - 1].strip() == "self._start_ui_queue_pump()"
    assert lines[destroy_call.lineno - 1].strip() == "root.destroy()"

    init_indent = lines[pump_call.lineno - 1][: len(lines[pump_call.lineno - 1]) - len(lines[pump_call.lineno - 1].lstrip())]
    destroy_indent = lines[destroy_call.lineno - 1][: len(lines[destroy_call.lineno - 1]) - len(lines[destroy_call.lineno - 1].lstrip())]

    init_replacement = [
        f"{init_indent}self._tk_shutdown_started = False",
        f"{init_indent}self._ui_queue_after_id = None",
        f"{init_indent}try:",
        f"{init_indent}    root.protocol(\"WM_DELETE_WINDOW\", self._destroy_root_safely)",
        f"{init_indent}except Exception as __spina_exc:",
        f"{init_indent}    _log_suppressed_once('tk_shutdown_protocol', 'Tk shutdown protocol setup failed', __spina_exc)",
        f"{init_indent}self._start_ui_queue_pump()",
    ]

    methods_replacement = textwrap.dedent(
        '''
        def _prepare_tk_shutdown(self):
            """Cancel recurring Tk callbacks before the root interpreter is destroyed."""
            if getattr(self, "_tk_shutdown_started", False):
                return
            self._tk_shutdown_started = True

            after_id = getattr(self, "_ui_queue_after_id", None)
            self._ui_queue_after_id = None
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass

            try:
                if self.root.winfo_exists():
                    self.root.update_idletasks()
            except Exception:
                pass

        def _destroy_root_safely(self):
            """Finish pending ttk idle work, cancel timers, then destroy the root once."""
            self._prepare_tk_shutdown()
            try:
                if self.root.winfo_exists():
                    self.root.destroy()
            except Exception:
                pass

        def _start_ui_queue_pump(self):
            """Process UI-call requests from worker threads on the Tk main thread."""
            def _schedule_next():
                if getattr(self, "_tk_shutdown_started", False):
                    self._ui_queue_after_id = None
                    return
                try:
                    if self.root.winfo_exists():
                        self._ui_queue_after_id = self.root.after(50, _pump)
                    else:
                        self._ui_queue_after_id = None
                except Exception as __spina_exc:
                    self._ui_queue_after_id = None
                    _log_suppressed_once('ui_queue_pump_schedule', 'UI queue pump scheduling stopped', __spina_exc)

            def _pump():
                self._ui_queue_after_id = None
                if getattr(self, "_tk_shutdown_started", False):
                    return
                try:
                    while True:
                        func, args, kwargs, ev, out = self._ui_queue.get_nowait()
                        try:
                            out["result"] = func(*args, **kwargs)
                        except Exception as e:
                            out["exc"] = e
                        finally:
                            try:
                                ev.set()
                            except Exception as __spina_exc:
                                _log_suppressed_once('excpass_0275', 'suppressed exception excpass_0275', __spina_exc)
                except queue.Empty:
                    pass
                except Exception as e:
                    try:
                        _log_exc("ui_queue_pump", e)
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0276', 'suppressed exception excpass_0276', __spina_exc)
                _schedule_next()

            _schedule_next()
        '''
    ).strip("\n")
    methods_replacement = textwrap.indent(methods_replacement, "    ").splitlines()

    replacements = [
        (pump.lineno - 1, pump.end_lineno, methods_replacement),
        (destroy_call.lineno - 1, destroy_call.lineno, [f"{destroy_indent}self._destroy_root_safely()"]),
        (pump_call.lineno - 1, pump_call.lineno, init_replacement),
    ]
    for start, end, replacement in sorted(replacements, reverse=True):
        lines[start:end] = replacement

    updated = newline.join(lines) + (newline if text.endswith(("\n", "\r\n")) else "")
    assert updated.count("def _prepare_tk_shutdown(self):") == 1
    assert updated.count("def _destroy_root_safely(self):") == 1
    assert updated.count("root.protocol(\"WM_DELETE_WINDOW\", self._destroy_root_safely)") == 1
    assert updated.count("self.root.after_cancel(after_id)") == 1
    assert updated.count("self._ui_queue_after_id = self.root.after(50, _pump)") == 1
    assert "                    root.destroy()" not in updated
    DESKTOP.write_text(updated, encoding="utf-8", newline="")

    test_text = r'''from __future__ import annotations

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
    assert text.count("self.root.after_cancel(after_id)") == 1
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
'''
    TEST.write_text(test_text, encoding="utf-8")
    print("Prepared guarded Wave 46 Tk shutdown repair and regression test.")


if __name__ == "__main__":
    main()
