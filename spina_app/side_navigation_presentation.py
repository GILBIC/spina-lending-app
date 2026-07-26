"""Side-navigation presentation extracted in Wave 48."""
from __future__ import annotations

import os
import tkinter as tk

_SIDE_NAVIGATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "os", "tk",
    "_SIDE_NAVIGATION_DEPENDENCIES", "_PROTECTED_GLOBALS",
    "configure_side_navigation_dependencies",
    "SIDE_NAVIGATION_TARGETS", "SIDE_NAVIGATION_SOURCE_LINES",
    "SIDE_NAVIGATION_SOURCE_SHA256", "SIDE_NAVIGATION_SIGNATURES",
    "SIDE_NAVIGATION_CALLS", "SIDE_NAVIGATION_TOTAL_SOURCE_LINES",
    "_spina_v13_hide_main_notebook_tabs", "_spina_v13_side_nav_items",
    "_spina_v13_rebuild_side_nav", "_spina_v13_refresh_side_nav_selection",
    "_spina_v13_setup_style", "_spina_v13_apply_ui_theme",
}


def configure_side_navigation_dependencies(namespace):
    _SIDE_NAVIGATION_DEPENDENCIES.clear()
    _SIDE_NAVIGATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

SIDE_NAVIGATION_TARGETS = ['_spina_v13_hide_main_notebook_tabs', '_spina_v13_side_nav_items', '_spina_v13_rebuild_side_nav', '_spina_v13_refresh_side_nav_selection', '_spina_v13_setup_style', '_spina_v13_apply_ui_theme']
SIDE_NAVIGATION_SOURCE_LINES = {'_spina_v13_hide_main_notebook_tabs': 28, '_spina_v13_side_nav_items': 32, '_spina_v13_rebuild_side_nav': 99, '_spina_v13_refresh_side_nav_selection': 30, '_spina_v13_setup_style': 7, '_spina_v13_apply_ui_theme': 8}
SIDE_NAVIGATION_SOURCE_SHA256 = {'_spina_v13_hide_main_notebook_tabs': '62fe7625905ea293f37e7bd3128aaef64b589a797628955d1b3f2c83eb9982dd', '_spina_v13_side_nav_items': 'af8615304dd0219ad93bd0ad8269f553fbb5120c05550d3d1253f5b1017f6a67', '_spina_v13_rebuild_side_nav': 'f41ca714d7123c3a82188c788a1973b4e6b85ea5bc51a38321d2757c9ffb0504', '_spina_v13_refresh_side_nav_selection': '9eb3edef07caef16a5b0139ce1b584e8ef2494d032e6a958d8b79bdcdb576ea1', '_spina_v13_setup_style': '7dbacc332c577d69bb553d2ee4e2ccaaa75ec74e1bcbbe45caf85e1c1aed6d69', '_spina_v13_apply_ui_theme': 'a00a234ffd6a60002dcb7d94c183e54deb5b3e890fd5e3a2e3ff81f57896b566'}
SIDE_NAVIGATION_SIGNATURES = {'_spina_v13_hide_main_notebook_tabs': 'self', '_spina_v13_side_nav_items': 'self', '_spina_v13_rebuild_side_nav': 'self', '_spina_v13_refresh_side_nav_selection': 'self', '_spina_v13_setup_style': 'self, *args, **kwargs', '_spina_v13_apply_ui_theme': 'self, *args, **kwargs'}
SIDE_NAVIGATION_CALLS = {'_spina_v13_hide_main_notebook_tabs': ['_log_suppressed_once', '_ttk.Style', 'getattr', 'nb.configure', 'st.configure', 'st.layout'], '_spina_v13_side_nav_items': ['getattr', 'icons.get', 'items.append', 'list', 'nb.tab', 'nb.tabs', 'str', 'strip'], '_spina_v13_rebuild_side_nav': ['_log_suppressed_once', '_spina_v13_hide_main_notebook_tabs', '_spina_v13_side_nav_items', 'bottom.pack', 'btn.pack', 'child.destroy', 'frame.configure', 'frame.pack_propagate', 'frame.winfo_children', 'getattr', 'lbl.pack', 'lower', 'p.get', 'self._refresh_side_nav_selection', 'self._select_side_tab', 'self._side_nav_labels.append', 'self._theme_palette', 'sep.pack', 'sep2.pack', 'startswith', 'str', 'strip', 'subtitle.pack', 'title.pack', 'tk.Button', 'tk.Frame', 'tk.Label'], '_spina_v13_refresh_side_nav_selection': ['btn.configure', 'buttons.items', 'getattr', 'list', 'lower', 'p.get', 'self._theme_palette', 'self.nb.select', 'startswith', 'str'], '_spina_v13_setup_style': ['_spina_v13_hide_main_notebook_tabs', '_spina_v13_orig_setup_style'], '_spina_v13_apply_ui_theme': ['_spina_v13_hide_main_notebook_tabs', '_spina_v13_orig_apply_theme', '_spina_v13_rebuild_side_nav']}
SIDE_NAVIGATION_TOTAL_SOURCE_LINES = 204

def _spina_v13_hide_main_notebook_tabs(self):
        try:
            import tkinter.ttk as _ttk
            st = _ttk.Style(getattr(self, 'root', None) or None)
            # Create/refresh a style used only by the main app notebook.
            for sty in ('SideOnly.TNotebook', 'Sidebar.TNotebook'):
                try:
                    st.configure(sty, borderwidth=0, tabmargins=(0, 0, 0, 0))
                except Exception:
                    pass
                try:
                    st.layout(sty + '.Tab', [])
                except Exception:
                    pass
            nb = getattr(self, 'nb', None)
            if nb is not None:
                try:
                    nb.configure(style='SideOnly.TNotebook')
                except Exception:
                    try:
                        nb.configure(style='Sidebar.TNotebook')
                    except Exception:
                        pass
        except Exception as e:
            try:
                _log_suppressed_once('v13_hide_tabs', 'hide main notebook tabs failed', e)
            except Exception:
                pass

def _spina_v13_side_nav_items(self):
        """Return every visible main notebook pane as a sidebar item."""
        icons = {
            'Data Bank': '▦',
            'Dashboard': '◈',
            'Cash Control': '₱',
            'Reports': '▤',
            'Clients': '◉',
            'Client Info Logs': '▣',
            "Collector's Route": '⌁',
            'Audit': '✓',
            'Data': '⚙',
        }
        items = []
        nb = getattr(self, 'nb', None)
        if nb is None:
            return items
        try:
            tabs = list(nb.tabs())
        except Exception:
            tabs = []
        for tab in tabs:
            try:
                state = str(nb.tab(tab, 'state') or 'normal')
                if state == 'hidden':
                    continue
                title = str(nb.tab(tab, 'text') or '').strip() or 'Page'
                icon = icons.get(title, '•')
                items.append((tab, title, icon))
            except Exception:
                continue
        return items

def _spina_v13_rebuild_side_nav(self):
        """Modern sidebar rebuild: all visible tabs live here, no top tab row."""
        try:
            _spina_v13_hide_main_notebook_tabs(self)
        except Exception:
            pass
        frame = getattr(self, 'sidebar_frame', None)
        if frame is None:
            return
        try:
            for child in frame.winfo_children():
                child.destroy()
        except Exception:
            pass

        try:
            p = getattr(self, '_ui_colors', None) or self._theme_palette()
        except Exception:
            p = {'bg': '#111217', 'panel': '#181a20', 'fg': '#ffffff', 'muted': '#a9a9b3', 'accent': '#ffd1e6', 'border': '#30323a', 'button_active': '#2a2d36'}

        is_dark = str(getattr(self, 'ui_theme', 'dark')).lower().startswith('d')
        panel = p.get('panel', '#181a20' if is_dark else '#ffffff')
        fg = p.get('fg', '#ffffff' if is_dark else '#1a1a1a')
        muted = p.get('muted', '#a9a9b3' if is_dark else '#666666')
        border = p.get('border', '#30323a' if is_dark else '#dddddd')

        try:
            frame.configure(width=215)
            frame.pack_propagate(False)
        except Exception:
            pass

        self._side_nav_buttons = {}
        self._side_nav_labels = []
        family = 'Segoe UI' if os.name == 'nt' else 'TkDefaultFont'

        # Logo / title block
        try:
            title = tk.Label(frame, text='SPINA', anchor='w', bg=panel, fg=fg,
                             font=(family, 16, 'bold'), padx=12, pady=4)
            title.pack(fill='x', pady=(0, 0))
            self._side_nav_labels.append(title)
        except Exception:
            pass
        try:
            subtitle = tk.Label(frame, text='PostgreSQL Edition', anchor='w', bg=panel, fg=muted,
                                font=(family, 9), padx=12, pady=0)
            subtitle.pack(fill='x', pady=(0, 12))
            self._side_nav_labels.append(subtitle)
        except Exception:
            pass
        try:
            sep = tk.Frame(frame, bg=border, height=1)
            sep.pack(fill='x', padx=8, pady=(0, 10))
        except Exception:
            pass

        for tab, title, icon in _spina_v13_side_nav_items(self):
            try:
                btn = tk.Button(
                    frame,
                    text=f'  {icon}  {title}',
                    anchor='w',
                    relief='flat',
                    bd=0,
                    padx=12,
                    pady=11,
                    cursor='hand2',
                    font=(family, 10, 'bold'),
                    command=lambda t=tab: self._select_side_tab(t),
                )
                btn.pack(fill='x', pady=3, padx=4)
                self._side_nav_buttons[str(tab)] = btn
            except Exception as e:
                try:
                    _log_suppressed_once('v13_side_nav_button', 'sidebar button failed', e)
                except Exception:
                    pass

        try:
            bottom = tk.Frame(frame, bg=panel)
            bottom.pack(side='bottom', fill='x', pady=(12, 0))
            try:
                sep2 = tk.Frame(bottom, bg=border, height=1)
                sep2.pack(fill='x', padx=8, pady=(0, 8))
            except Exception:
                pass
            role_text = f"{getattr(self, 'user_name', '')} • {getattr(self, 'user_role', '')}".strip(' •')
            lbl = tk.Label(bottom, text=role_text, anchor='w', bg=panel, fg=muted,
                           font=(family, 8), padx=12, pady=4, wraplength=175)
            lbl.pack(fill='x')
            self._side_nav_labels.append(lbl)
        except Exception:
            pass

        try:
            self._refresh_side_nav_selection()
        except Exception:
            pass

def _spina_v13_refresh_side_nav_selection(self):
        buttons = getattr(self, '_side_nav_buttons', {}) or {}
        if not buttons:
            return
        try:
            selected = str(self.nb.select())
        except Exception:
            selected = ''
        try:
            p = getattr(self, '_ui_colors', None) or self._theme_palette()
        except Exception:
            p = {'panel': '#181a20', 'fg': '#ffffff', 'muted': '#a9a9b3', 'accent': '#ffd1e6', 'button_active': '#2a2d36'}
        is_dark = str(getattr(self, 'ui_theme', 'dark')).lower().startswith('d')
        normal_bg = p.get('panel', '#181a20' if is_dark else '#ffffff')
        normal_fg = p.get('fg', '#ffffff' if is_dark else '#1a1a1a')
        selected_bg = '#343842' if is_dark else p.get('accent', '#ffd1e6')
        selected_fg = '#ffffff' if is_dark else '#1a1a1a'
        hover_bg = p.get('button_active', '#2a2d36' if is_dark else '#f3e6eb')
        for tid, btn in list(buttons.items()):
            try:
                active = (tid == selected)
                btn.configure(
                    bg=selected_bg if active else normal_bg,
                    fg=selected_fg if active else normal_fg,
                    activebackground=hover_bg,
                    activeforeground=selected_fg if active else normal_fg,
                    highlightthickness=0,
                )
            except Exception:
                pass

def _spina_v13_setup_style(self, *args, **kwargs):
                res = _spina_v13_orig_setup_style(self, *args, **kwargs)
                try:
                    _spina_v13_hide_main_notebook_tabs(self)
                except Exception:
                    pass
                return res

def _spina_v13_apply_ui_theme(self, *args, **kwargs):
                res = _spina_v13_orig_apply_theme(self, *args, **kwargs)
                try:
                    _spina_v13_hide_main_notebook_tabs(self)
                    _spina_v13_rebuild_side_nav(self)
                except Exception:
                    pass
                return res
