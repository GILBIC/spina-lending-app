from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk

IMPORT_LOG_TARGET = '_show_import_log_window'
IMPORT_LOG_SOURCE_LINES = 337
IMPORT_LOG_SOURCE_SHA256 = '017ec81edcd4d086f905ce5a147a0a0855073f354ed63955d171aa15ed22c912'
IMPORT_LOG_CALLERS = ('App._import_encoder_batch',)

_log_suppressed_once = None
_open_path = None
DATA_DIR = None


def configure_import_log_dependencies(namespace) -> None:
    global _log_suppressed_once, _open_path, DATA_DIR
    _log_suppressed_once = namespace["_log_suppressed_once"]
    _open_path = namespace["_open_path"]
    DATA_DIR = namespace["DATA_DIR"]


def _show_import_log_window(self, title: str, summary: str, lines, default_save_path: str | None = None):
        """Organized import log viewer (tabs + search + save/copy).

        Tabs:
          - All (chronological)
          - Inserted / Updated
          - Skipped Duplicates / Skipped Unknown / Skipped
          - Errors
          - Header/Info / Other
        """
        import os
        try:
            parent = getattr(self, "root", None)
            win = tk.Toplevel(parent)
        except Exception:
            # No UI available: best-effort save only
            try:
                if default_save_path:
                    os.makedirs(os.path.dirname(default_save_path) or ".", exist_ok=True)
                    with open(default_save_path, "w", encoding="utf-8") as f:
                        if summary:
                            f.write(str(summary) + "\n\n")
                        for ln in (lines or []):
                            f.write(str(ln) + "\n")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_0001', 'suppressed exception excpass_importlog_0001', __spina_exc)
            return

        def _classify(ln: str) -> str:
            s = (ln or "").strip()
            up = s.upper()
            if "ERROR" in up and ("] ERROR" in up or "ERROR:" in up):
                return "Errors"
            if "SKIP_UNKNOWN" in up:
                return "Skipped Unknown"
            if "SKIP_DUP" in up:
                return "Skipped Duplicates"
            if "SKIP" in up and ("SKIP:" in up or "SKIP_" in up):
                return "Skipped"
            if "INSERTED" in up:
                return "Inserted"
            if "UPDATED" in up:
                return "Updated"
            if s.startswith("FILE:") or s.startswith("START:") or s.startswith("END:") or s.startswith("-" * 10):
                return "Header/Info"
            return "Other"

        all_lines = [str(x) for x in (lines or [])]

        # Build groups
        groups = {
            "All": list(all_lines),
            "Inserted": [],
            "Updated": [],
            "Skipped Duplicates": [],
            "Skipped Unknown": [],
            "Skipped": [],
            "Errors": [],
            "Header/Info": [],
            "Other": [],
        }
        for ln in all_lines:
            cat = _classify(ln)
            if cat in groups and cat != "All":
                groups[cat].append(ln)
            else:
                groups["Other"].append(ln)

        # UI scaffold
        try:
            win.title(title or "Import Log")
            win.geometry("980x640")
        except Exception:
            pass

        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        # Summary header (always visible)
        if summary:
            summary_box = ttk.Label(outer, text=str(summary), justify="left")
            summary_box.pack(fill="x", pady=(0, 8))

        # Controls row
        ctrl = ttk.Frame(outer)
        ctrl.pack(fill="x", pady=(0, 8))

        ttk.Label(ctrl, text="Search:").pack(side="left")
        search_var = tk.StringVar()
        search_entry = ttk.Entry(ctrl, textvariable=search_var, width=44)
        search_entry.pack(side="left", padx=(6, 10))

        search_all_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="Filter all tabs", variable=search_all_var).pack(side="left")

        status_var = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=status_var).pack(side="right")

        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)

        tab_order = ["All", "Inserted", "Updated", "Skipped Duplicates", "Skipped Unknown", "Skipped", "Errors", "Header/Info", "Other"]
        tab_frames = {}
        tab_text = {}

        def _make_tab(cat: str):
            frm = ttk.Frame(nb)
            nb.add(frm, text=f"{cat} ({len(groups.get(cat, []))})")
            tab_frames[cat] = frm

            text_frame = ttk.Frame(frm)
            text_frame.pack(fill="both", expand=True)

            txt = tk.Text(text_frame, wrap="none")
            vsb = ttk.Scrollbar(text_frame, orient="vertical", command=txt.yview)
            hsb = ttk.Scrollbar(text_frame, orient="horizontal", command=txt.xview)
            txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

            txt.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            hsb.grid(row=1, column=0, sticky="ew")
            text_frame.rowconfigure(0, weight=1)
            text_frame.columnconfigure(0, weight=1)

            try:
                txt.configure(state="disabled")
            except Exception:
                pass

            tab_text[cat] = txt

        for cat in tab_order:
            _make_tab(cat)

        def _render(cat: str):
            q = (search_var.get() or "").strip().lower()
            base = groups.get(cat, []) or []
            if q:
                view = [ln for ln in base if q in ln.lower()]
            else:
                view = list(base)

            txt = tab_text.get(cat)
            if not txt:
                return 0, len(base)

            try:
                txt.configure(state="normal")
                txt.delete("1.0", "end")
                for ln in view:
                    txt.insert("end", ln + "\n")
                txt.configure(state="disabled")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_render', 'suppressed exception excpass_importlog_render', __spina_exc)
            return len(view), len(base)

        def _current_cat() -> str:
            try:
                idx = nb.index("current")
                return tab_order[idx]
            except Exception:
                return "All"

        def _refresh(*_):
            try:
                if search_all_var.get():
                    # Refresh every tab
                    for cat in tab_order:
                        _render(cat)
                    cur = _current_cat()
                    shown, total = _render(cur)
                else:
                    cur = _current_cat()
                    shown, total = _render(cur)
                status_var.set(f"Showing {shown} / {total} in '{_current_cat()}'")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_refresh', 'suppressed exception excpass_importlog_refresh', __spina_exc)

        # File ops
        def _build_save_text(mode: str = "all", cat: str | None = None) -> str:
            # mode: "all" or "visible"
            q = (search_var.get() or "").strip().lower()
            parts = []
            if summary:
                parts.append(str(summary).rstrip())
                parts.append("")
            if mode == "visible" and cat:
                base = groups.get(cat, []) or []
                if q:
                    base = [ln for ln in base if q in ln.lower()]
                parts.extend(base)
                return "\n".join(parts).rstrip() + "\n"

            # all: include chronological + organized sections
            parts.append("== CHRONOLOGICAL ==")
            parts.extend(all_lines)
            parts.append("")
            parts.append("== ORGANIZED ==")
            for c in tab_order:
                if c == "All":
                    continue
                sec = groups.get(c, []) or []
                if not sec:
                    continue
                parts.append(f"-- {c} ({len(sec)}) --")
                parts.extend(sec)
                parts.append("")
            return "\n".join(parts).rstrip() + "\n"

        def _write_to(pth: str, mode: str = "all", cat: str | None = None) -> bool:
            try:
                pth = str(pth or "").strip()
                if not pth:
                    return False
                os.makedirs(os.path.dirname(pth) or ".", exist_ok=True)
                with open(pth, "w", encoding="utf-8") as f:
                    f.write(_build_save_text(mode=mode, cat=cat))
                return True
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_write', 'suppressed exception excpass_importlog_write', __spina_exc)
                return False

        saved_path = None
        if default_save_path:
            try:
                if os.path.exists(default_save_path):
                    saved_path = default_save_path
                elif _write_to(default_save_path, mode="all"):
                    saved_path = default_save_path
            except Exception:
                saved_path = None

        def _copy_visible():
            try:
                cat = _current_cat()
                data = _build_save_text(mode="visible", cat=cat)
                win.clipboard_clear()
                win.clipboard_append(data)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_copy_vis', 'suppressed exception excpass_importlog_copy_vis', __spina_exc)

        def _copy_all():
            try:
                data = _build_save_text(mode="all")
                win.clipboard_clear()
                win.clipboard_append(data)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_copy_all', 'suppressed exception excpass_importlog_copy_all', __spina_exc)

        def _save_visible_as():
            try:
                cat = _current_cat()
                pth = filedialog.asksaveasfilename(
                    parent=win,
                    title="Save visible log",
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                )
                if not pth:
                    return
                if _write_to(pth, mode="visible", cat=cat):
                    win._spina_saved_import_log_path = pth  # type: ignore[attr-defined]
                    try:
                        btn_open.configure(state="normal")
                    except Exception:
                        pass
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_save_vis', 'suppressed exception excpass_importlog_save_vis', __spina_exc)

        def _save_all_as():
            try:
                pth = filedialog.asksaveasfilename(
                    parent=win,
                    title="Save full (organized) log",
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                )
                if not pth:
                    return
                if _write_to(pth, mode="all"):
                    win._spina_saved_import_log_path = pth  # type: ignore[attr-defined]
                    try:
                        btn_open.configure(state="normal")
                    except Exception:
                        pass
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_save_all', 'suppressed exception excpass_importlog_save_all', __spina_exc)

        def _open_saved():
            try:
                pth = getattr(win, "_spina_saved_import_log_path", None) or saved_path
                if pth:
                    _open_path(pth)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_open', 'suppressed exception excpass_importlog_open', __spina_exc)

        def _open_data_folder():
            try:
                _open_path(DATA_DIR)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_importlog_folder', 'suppressed exception excpass_importlog_folder', __spina_exc)

        btn_row = ttk.Frame(outer)
        btn_row.pack(fill="x", pady=(8, 0))

        ttk.Button(btn_row, text="Copy Visible", command=_copy_visible).pack(side="left")
        ttk.Button(btn_row, text="Copy All", command=_copy_all).pack(side="left", padx=(8, 0))
        ttk.Button(btn_row, text="Save Visible…", command=_save_visible_as).pack(side="left", padx=(8, 0))
        ttk.Button(btn_row, text="Save All…", command=_save_all_as).pack(side="left", padx=(8, 0))

        btn_open = ttk.Button(btn_row, text="Open Saved Log", command=_open_saved)
        btn_open.pack(side="left", padx=(8, 0))

        ttk.Button(btn_row, text="Open Data Folder", command=_open_data_folder).pack(side="left", padx=(8, 0))
        ttk.Button(btn_row, text="Close", command=win.destroy).pack(side="right")

        try:
            if saved_path:
                win._spina_saved_import_log_path = saved_path  # type: ignore[attr-defined]
                btn_open.configure(state="normal")
            else:
                btn_open.configure(state="disabled")
        except Exception:
            pass

        try:
            search_entry.bind("<KeyRelease>", _refresh)
            nb.bind("<<NotebookTabChanged>>", _refresh)
        except Exception:
            pass

        # Initial render
        try:
            search_entry.focus_set()
        except Exception:
            pass
        _refresh()
