"""Navigation presentation helpers extracted from the SPINA desktop entry module."""

from __future__ import annotations

import calendar
import os
import tkinter as tk
from tkinter import ttk


def _noop_log(*args, **kwargs):
    return None


_log_suppressed_once = _noop_log


def fmt_currency(value):
    return str(value)


def configure_navigation_dependencies(*, log_suppressed_once, fmt_currency_callback):
    """Bind application-owned logging and currency display helpers."""
    global _log_suppressed_once, fmt_currency
    _log_suppressed_once = log_suppressed_once or _noop_log
    fmt_currency = fmt_currency_callback or str


def _update_data_toolbar(self, *args, **kwargs):
    try:
        var = getattr(self, '_db_close_info_var', None)
        if not var:
            return
        ds = self._get_databank_focus_date()
        if not ds:
            var.set('')
            return
        rec = None
        try:
            rec = self.db.get_databank_day_close(ds) if hasattr(self, 'db') else None
        except Exception:
            rec = None
        if rec:
            try:
                variance = float(rec.get('variance') or 0.0)
            except Exception:
                variance = 0.0
            lock_txt = 'CLOSED' if bool(int(rec.get('is_closed') or 0)) else 'OPEN'
            stat_txt = (rec.get('variance_status') or 'Balanced').strip() or 'Balanced'
            var_txt = fmt_currency(abs(variance)) if abs(variance) >= 0.005 else fmt_currency(0)
            wf_txt = (rec.get('variance_workflow_status') or 'Open').strip() or 'Open'
            var.set(f"{ds} · Combined · {lock_txt} · {wf_txt} · {stat_txt} {var_txt}")
        else:
            var.set(f"{ds} · Combined · not closed")
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_dayclose_toolbar', 'suppressed exception excpass_dayclose_toolbar', __spina_exc)
        pass


def _side_nav_items(self):
    """Return visible main tabs as (tab_widget, title, icon)."""
    specs = [
        (getattr(self, 'tab_data', None), 'Data Bank', '▦'),
        (getattr(self, 'tab_reports', None), 'Reports', '▤'),
        (getattr(self, 'tab_clients', None), 'Clients', '◉'),
        (getattr(self, 'tab_collectors', None), "Collector's Route", '⌁'),
        (getattr(self, 'tab_audit', None), 'Audit', '✓'),
        (getattr(self, 'tab_system_data', None), 'Data', '⚙'),
    ]
    items = []
    try:
        tabs = set(str(t) for t in self.nb.tabs())
    except Exception:
        tabs = set()
    for tab, title, icon in specs:
        if tab is None:
            continue
        try:
            tid = str(tab)
            if tid not in tabs:
                continue
            state = str(self.nb.tab(tab, 'state') or 'normal')
            if state == 'hidden':
                continue
            items.append((tab, title, icon))
        except Exception as __spina_exc:
            __spina_logger = globals().get('_log_suppressed_once')
            if callable(__spina_logger):
                __spina_logger('silent_ui_15857__side_nav_items', 'suppressed UI/startup exception at line 15857', __spina_exc)
            continue
    return items


def _rebuild_side_nav(self):
    """Rebuild the modern left-side navigation from the currently visible notebook tabs."""
    frame = getattr(self, 'sidebar_frame', None)
    if frame is None:
        return
    try:
        for child in frame.winfo_children():
            child.destroy()
    except Exception as __spina_exc:
        _log_suppressed_once('modern_ui_pass_15902', 'modern UI sidebar child cleanup skipped', __spina_exc)
        pass

    try:
        p = getattr(self, '_ui_colors', None) or self._theme_palette()
    except Exception:
        p = {'bg': '#f7f7fb', 'panel': '#ffffff', 'fg': '#1a1a1a', 'muted': '#666666', 'accent': '#ffd1e6', 'border': '#dddddd'}

    try:
        frame.configure(width=190)
        frame.pack_propagate(False)
    except Exception as __spina_exc:
        _log_suppressed_once('modern_ui_pass_15913', 'modern UI sidebar frame layout skipped', __spina_exc)
        pass

    # App label inside sidebar
    try:
        title = tk.Label(
            frame,
            text='SPINA',
            anchor='w',
            bg=p.get('panel', '#ffffff'),
            fg=p.get('fg', '#1a1a1a'),
            font=('Segoe UI' if os.name == 'nt' else 'TkDefaultFont', 15, 'bold'),
            padx=8,
            pady=4,
        )
        title.pack(fill='x', pady=(0, 2))
        self._side_nav_labels.append(title)
    except Exception:
        pass

    try:
        subtitle = tk.Label(
            frame,
            text='PostgreSQL Edition',
            anchor='w',
            bg=p.get('panel', '#ffffff'),
            fg=p.get('muted', '#666666'),
            font=('Segoe UI' if os.name == 'nt' else 'TkDefaultFont', 9),
            padx=8,
            pady=0,
        )
        subtitle.pack(fill='x', pady=(0, 12))
        self._side_nav_labels.append(subtitle)
    except Exception as __spina_exc:
        _log_suppressed_once('modern_ui_pass_15946', 'modern UI sidebar subtitle build skipped', __spina_exc)
        pass

    self._side_nav_buttons = {}
    family = 'Segoe UI' if os.name == 'nt' else 'TkDefaultFont'
    for tab, title, icon in self._side_nav_items():
        try:
            btn = tk.Button(
                frame,
                text=f'  {icon}  {title}',
                anchor='w',
                relief='flat',
                bd=0,
                padx=10,
                pady=10,
                cursor='hand2',
                font=(family, 10, 'bold'),
                command=lambda t=tab: self._select_side_tab(t),
            )
            btn.pack(fill='x', pady=3)
            self._side_nav_buttons[str(tab)] = btn
        except Exception as e:
            try:
                _log_suppressed_once('side_nav_btn', 'sidebar button failed', e)
            except Exception as __spina_exc:
                _log_suppressed_once('modern_ui_pass_15970', 'modern UI sidebar button logging fallback skipped', __spina_exc)
                pass

    try:
        bottom = ttk.Frame(frame, style='Sidebar.TFrame')
        bottom.pack(side='bottom', fill='x', pady=(12, 0))
        role_text = f"{getattr(self, 'user_name', '')} • {getattr(self, 'user_role', '')}"
        lbl = tk.Label(
            bottom,
            text=role_text,
            anchor='w',
            bg=p.get('panel', '#ffffff'),
            fg=p.get('muted', '#666666'),
            font=(family, 8),
            padx=8,
            pady=4,
            wraplength=160,
        )
        lbl.pack(fill='x')
        self._side_nav_labels.append(lbl)
    except Exception as __spina_exc:
        _log_suppressed_once('modern_ui_pass_15990', 'modern UI sidebar user label build skipped', __spina_exc)
        pass

    self._refresh_side_nav_selection()


def _refresh_side_nav_selection(self):
    """Update sidebar button colors to match the selected notebook tab."""
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
        p = {'panel': '#ffffff', 'fg': '#1a1a1a', 'muted': '#666666', 'accent': '#ffd1e6', 'button_active': '#f3e6eb'}
    is_dark = str(getattr(self, 'ui_theme', 'light')).lower().startswith('d')
    normal_bg = p.get('panel', '#ffffff')
    normal_fg = p.get('fg', '#1a1a1a')
    selected_bg = '#3a3d46' if is_dark else p.get('accent', '#ffd1e6')
    selected_fg = '#ffffff' if is_dark else '#1a1a1a'
    hover_bg = p.get('button_active', selected_bg)
    for tid, btn in list(buttons.items()):
        try:
            active = (tid == selected)
            bg = selected_bg if active else normal_bg
            fg = selected_fg if active else normal_fg
            btn.configure(
                bg=bg,
                fg=fg,
                activebackground=hover_bg,
                activeforeground=fg,
                highlightthickness=0,
            )
        except Exception as __spina_exc:
            _log_suppressed_once('modern_ui_pass_16026', 'modern UI sidebar button selection style skipped', __spina_exc)
            pass


def _header_palette(self):
    """Compact color palette for the modern top header."""
    try:
        base = getattr(self, '_ui_colors', None) or self._theme_palette()
    except Exception:
        base = {}
    try:
        dark = str(getattr(self, 'ui_theme', 'dark')).lower().startswith('d')
    except Exception:
        dark = True
    if dark:
        return {
            'bg': '#15161c',
            'panel': '#1f2028',
            'panel2': '#272936',
            'fg': '#f4f5f7',
            'muted': '#aeb3c2',
            'border': '#333746',
            'accent': '#ff7ab6',
            'accent2': '#22c55e',
            'chip': '#2b2e3b',
            'chip_active': '#ff7ab6',
            'chip_active_fg': '#1b0f16',
            'button': '#242734',
            'button_hover': '#313545',
            'danger': '#f87171',
        }
    return {
        'bg': '#f7f8fb',
        'panel': '#ffffff',
        'panel2': '#f1f5f9',
        'fg': '#111827',
        'muted': '#64748b',
        'border': '#d8dee9',
        'accent': '#ec4899',
        'accent2': '#16a34a',
        'chip': '#eef2f7',
        'chip_active': '#ec4899',
        'chip_active_fg': '#ffffff',
        'button': '#ffffff',
        'button_hover': '#f3f4f6',
        'danger': '#dc2626',
    }


def _make_header_button(self, master, text, command, *, primary=False, danger=False, width=None):
    """Create a flatter, modern top-bar button using tk.Button for better dark-mode control."""
    hp = self._header_palette()
    family = 'Segoe UI' if os.name == 'nt' else 'TkDefaultFont'
    bg = hp['accent'] if primary else (hp['danger'] if danger else hp['button'])
    fg = hp['chip_active_fg'] if primary else hp['fg']
    hover = '#f472b6' if primary else hp['button_hover']
    btn = tk.Button(
        master,
        text=text,
        command=command,
        relief='flat',
        bd=0,
        padx=12,
        pady=7,
        width=width or 0,
        cursor='hand2',
        bg=bg,
        fg=fg,
        activebackground=hover,
        activeforeground=fg,
        font=(family, 9, 'bold'),
        highlightthickness=1,
        highlightbackground=hp['border'],
    )
    self._tk_button_hover(btn, bg, hover)
    return btn


def _refresh_mode_toggle(self):
    """Update the Regular/7x7 segmented buttons after a mode change or theme change."""
    hp = self._header_palette()
    try:
        cur = '7x7' if self._mode_filter() == '7x7' else 'Regular'
    except Exception:
        cur = 'Regular'
    for key, btn in list((getattr(self, '_mode_buttons', {}) or {}).items()):
        try:
            active = (key == cur)
            bg = hp['chip_active'] if active else hp['chip']
            fg = hp['chip_active_fg'] if active else hp['fg']
            btn.configure(
                bg=bg,
                fg=fg,
                activebackground=bg,
                activeforeground=fg,
                highlightbackground=hp['accent'] if active else hp['border'],
            )
        except Exception as __spina_exc:
            _log_suppressed_once('modern_ui_pass_16176', 'modern UI mode button style skipped', __spina_exc)
            pass
    try:
        if getattr(self, 'mode_status_label', None) is not None:
            self.mode_status_label.configure(
                text=f"Current view: {cur}",
                bg=hp['panel'],
                fg=hp['muted'],
            )
    except Exception as __spina_exc:
        _log_suppressed_once('modern_ui_pass_16185', 'modern UI mode status label refresh skipped', __spina_exc)
        pass


def _vscroll(self, *args):
    try:
        self.name_tree.yview(*args)
        if self.days_tree: self.days_tree.yview(*args)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0368', 'suppressed exception excpass_0368', __spina_exc)
        pass


def _month_label(self):
    return f"{calendar.month_name[self.grid_month]} {self.grid_year}"


def _on_mousewheel_sync(self, event):
    """Mouse wheel scroll should move both name_tree (left) and days_tree (right) together."""
    try:
        delta = 0
        # Windows uses event.delta; on Linux it's often Button-4/5
        if hasattr(event, 'delta') and event.delta:
            delta = -1 if event.delta > 0 else 1
        elif getattr(event, 'num', None) in (4, 5):
            delta = -1 if event.num == 4 else 1
    
        name_tv = getattr(self, 'name_tree', None)
        days_tv = getattr(self, 'days_tree', None)
    
        if delta:
            if name_tv:
                try:
                    name_tv.yview_scroll(delta, 'units')
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0369', 'suppressed exception excpass_0369', __spina_exc)
                    pass
            if days_tv:
                try:
                    days_tv.yview_scroll(delta, 'units')
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0370', 'suppressed exception excpass_0370', __spina_exc)
                    pass
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0371', 'suppressed exception excpass_0371', __spina_exc)
        pass
    return 'break'


def _update_toolbar_states(self):
    try:
        if hasattr(self, "_del_client_btn"):
            has_sel = bool(self.clients_tree.selection())
            self._del_client_btn.config(state=("normal" if has_sel else "disabled"))
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0450', 'suppressed exception excpass_0450', __spina_exc)
        pass
