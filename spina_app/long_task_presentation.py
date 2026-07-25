"""Reusable long-running task presentation extracted in Wave 42."""
from __future__ import annotations

import inspect as _inspect
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

_LONG_TASK_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',
    '__name__', '__package__', '__spec__', '_LONG_TASK_DEPENDENCIES',
    '_PROTECTED_GLOBALS', 'configure_long_task_dependencies',
    'LONG_TASK_TARGET', 'LONG_TASK_SOURCE_LINES', 'LONG_TASK_SOURCE_SHA256',
    'LONG_TASK_NESTED_CALLBACKS', 'LONG_TASK_CALLS', 'LONG_TASK_CALLER_COUNT',
    '_inspect', 'threading', 'time', 'tk', 'messagebox', 'ttk',
}


def configure_long_task_dependencies(namespace):
    _LONG_TASK_DEPENDENCIES.clear()
    _LONG_TASK_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


LONG_TASK_TARGET = '_run_long_task'
LONG_TASK_SOURCE_LINES = 273
LONG_TASK_SOURCE_SHA256 = '037194095a785211335844178a4f90675c08d7cede51fa7675db4a9ccc17ac21'
LONG_TASK_NESTED_CALLBACKS = ['_cleanup_dialog', '_finish', '_request_cancel', '_watchdog', '_call_work_fn', '_worker']
LONG_TASK_CALLS = ['TimeoutError', '_call_work_fn', '_cleanup_dialog', '_finish', '_inspect.signature', '_log_exc', '_log_suppressed_once', 'any', 'box.get', 'btn_cancel.config', 'btn_cancel.pack', 'cancel_event.is_set', 'cancel_event.set', 'dlg.destroy', 'dlg.geometry', 'dlg.grab_release', 'dlg.grab_set', 'dlg.protocol', 'dlg.resizable', 'dlg.title', 'dlg.transient', 'dlg.update_idletasks', 'dlg.winfo_exists', 'dlg.winfo_height', 'dlg.winfo_width', 'done.get', 'float', 'frm.pack', 'int', 'len', 'list', 'max', 'messagebox.showerror', 'on_error', 'on_success', 'pack', 'pb.pack', 'pb.start', 'pb.stop', 'self.root.after', 'self.root.winfo_height', 'self.root.winfo_rootx', 'self.root.winfo_rooty', 'self.root.winfo_width', 'sig.parameters.values', 'start', 'str', 'threading.Event', 'threading.Thread', 'time.time', 'tk.Toplevel', 'ttk.Button', 'ttk.Frame', 'ttk.Label', 'ttk.Progressbar', 'work_fn']
LONG_TASK_CALLER_COUNT = 5

def _run_long_task(
    self,
    title: str,
    work_fn,
    on_success=None,
    on_error=None,
    allow_cancel: bool = True,
    timeout_s: float | None = None,
):
    """Run work_fn() in a background thread with a simple modal 'Please wait' dialog.

    Improvements:
      - Optional Cancel button (signals a cancel_event to work_fn if it supports it)
      - Optional timeout (prevents UI from hanging forever on stuck tasks)
      - Cleanup is guarded so it can't run twice
    """
    dlg = None
    pb = None
    btn_cancel = None
    cancel_event = threading.Event()

    box = {"result": None, "error": None, "cancelled": False}
    done = {"done": False}
    start_ts = time.time()

    def _cleanup_dialog():
        try:
            if pb is not None:
                pb.stop()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0285', 'suppressed exception excpass_0285', __spina_exc)
            pass
        try:
            if dlg is not None and dlg.winfo_exists():
                try:
                    dlg.grab_release()
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0286', 'suppressed exception excpass_0286', __spina_exc)
                    pass
                try:
                    dlg.destroy()
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0287', 'suppressed exception excpass_0287', __spina_exc)
                    pass
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0288', 'suppressed exception excpass_0288', __spina_exc)
            pass

    def _finish():
        # Guard: finish can be called from worker completion, cancel, or timeout.
        try:
            if done.get("done"):
                return
            done["done"] = True
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0289', 'suppressed exception excpass_0289', __spina_exc)
            pass

        _cleanup_dialog()

        # Cancelled: no popups, no callbacks
        try:
            if box.get("cancelled"):
                return
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0290', 'suppressed exception excpass_0290', __spina_exc)
            pass

        # Error path
        if box.get("error") is not None:
            if on_error:
                try:
                    on_error(box["error"])
                    return
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0291', 'suppressed exception excpass_0291', __spina_exc)
                    pass
            try:
                messagebox.showerror("Error", str(box["error"]))
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0292', 'suppressed exception excpass_0292', __spina_exc)
                pass
            return

        # Success path
        if on_success:
            try:
                on_success(box.get("result"))
            except Exception as e:
                try:
                    _log_exc("long_task:on_success", e)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0293', 'suppressed exception excpass_0293', __spina_exc)
                    pass

    def _request_cancel():
        try:
            if done.get("done"):
                return
            box["cancelled"] = True
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0294', 'suppressed exception excpass_0294', __spina_exc)
            pass
        try:
            cancel_event.set()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0295', 'suppressed exception excpass_0295', __spina_exc)
            pass
        try:
            if btn_cancel is not None:
                btn_cancel.config(state="disabled")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0296', 'suppressed exception excpass_0296', __spina_exc)
            pass
        # Close the dialog immediately (worker may still run; its _finish is guarded).
        try:
            _cleanup_dialog()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0297', 'suppressed exception excpass_0297', __spina_exc)
            pass

    def _watchdog():
        # Timeout watchdog runs on UI thread.
        try:
            if done.get("done"):
                return
            ts = float(timeout_s) if (timeout_s is not None) else None
            if ts and (time.time() - start_ts) > ts:
                try:
                    box["error"] = TimeoutError(f"Task timed out after {int(ts)} seconds.")
                except Exception:
                    box["error"] = TimeoutError("Task timed out.")
                try:
                    cancel_event.set()
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0298', 'suppressed exception excpass_0298', __spina_exc)
                    pass
                try:
                    self.root.after(0, _finish)
                except Exception:
                    try:
                        _finish()
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0299', 'suppressed exception excpass_0299', __spina_exc)
                        pass
                return
        except Exception as e:
            try:
                _log_exc("long_task:watchdog", e)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0300', 'suppressed exception excpass_0300', __spina_exc)
                pass
        try:
            self.root.after(250, _watchdog)
        except Exception:
            # root is likely closing
            pass

    # --- build dialog (UI thread) ---
    try:
        dlg = tk.Toplevel(self.root)
        dlg.title(title or "Please wait")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.root)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0301', 'suppressed exception excpass_0301', __spina_exc)
            pass
        try:
            dlg.grab_set()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0302', 'suppressed exception excpass_0302', __spina_exc)
            pass

        # Treat closing the window like Cancel (if allowed)
        try:
            if allow_cancel:
                dlg.protocol("WM_DELETE_WINDOW", _request_cancel)
            else:
                dlg.protocol("WM_DELETE_WINDOW", lambda: None)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0303', 'suppressed exception excpass_0303', __spina_exc)
            pass

        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=title or "Working...").pack(anchor="w")

        pb = ttk.Progressbar(frm, mode="indeterminate", length=320)
        pb.pack(fill="x", pady=(10, 0))
        pb.start(10)

        if allow_cancel:
            try:
                btn_cancel = ttk.Button(frm, text="Cancel", command=_request_cancel)
                btn_cancel.pack(anchor="e", pady=(10, 0))
            except Exception:
                btn_cancel = None

        try:
            dlg.update_idletasks()
            x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (dlg.winfo_width() // 2)
            y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (dlg.winfo_height() // 2)
            dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0304', 'suppressed exception excpass_0304', __spina_exc)
            pass
    except Exception:
        dlg = None
        pb = None

    # Start timeout watchdog (UI thread) if requested
    try:
        if timeout_s is not None:
            self.root.after(250, _watchdog)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0305', 'suppressed exception excpass_0305', __spina_exc)
        pass

    def _call_work_fn():
        """Call work_fn, optionally passing cancel_event if supported."""
        try:
            import inspect as _inspect
            try:
                sig = _inspect.signature(work_fn)
            except Exception:
                sig = None

            if sig:
                params = list(sig.parameters.values())
                has_varkw = any(p.kind == p.VAR_KEYWORD for p in params)
                if has_varkw or ("cancel_event" in sig.parameters):
                    return work_fn(cancel_event=cancel_event)
                # If it accepts exactly 1 positional arg, pass cancel_event
                pos = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
                if len(pos) == 1 and not any(p.kind == p.VAR_POSITIONAL for p in params):
                    return work_fn(cancel_event)
            # Default: no args
            return work_fn()
        except Exception:
            # If signature detection misfires (or work_fn hides signature), fall back
            return work_fn()

    def _worker():
        try:
            # If user already cancelled, skip starting the work
            try:
                if cancel_event.is_set():
                    box["cancelled"] = True
                    return
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0306', 'suppressed exception excpass_0306', __spina_exc)
                pass

            box["result"] = _call_work_fn()
        except Exception as e:
            box["error"] = e
            try:
                _log_exc(f"long_task:{title}", e)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0307', 'suppressed exception excpass_0307', __spina_exc)
                pass
        finally:
            try:
                self.root.after(0, _finish)
            except Exception:
                try:
                    _finish()
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0308', 'suppressed exception excpass_0308', __spina_exc)
                    pass

    threading.Thread(target=_worker, daemon=True).start()
