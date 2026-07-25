"""High-volume theme presentation helpers extracted in Wave 35."""
from __future__ import annotations

_THEME_PRESENTATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "_THEME_PRESENTATION_DEPENDENCIES",
    "_PROTECTED_GLOBALS", "configure_theme_presentation_dependencies",
    "THEME_PRESENTATION_SOURCE_SHA256", "THEME_PRESENTATION_TARGETS",
}


def configure_theme_presentation_dependencies(namespace):
    _THEME_PRESENTATION_DEPENDENCIES.clear()
    _THEME_PRESENTATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


THEME_PRESENTATION_TARGETS = ('_theme_toggle_text', '_theme_palette', '_apply_ui_theme', '_apply_tk_theme_recursive', '_refresh_modern_shell_theme', '_refresh_header_theme')
THEME_PRESENTATION_SOURCE_SHA256 = {
    "_apply_tk_theme_recursive": "87708debed3c355bd014e0f88dd15610951a28e8c84947f3104155864d4dcc60",
    "_apply_ui_theme": "6a664ebfbdcc0b72748da1f5f0d0153144b5fcb5f16ddafbf425bb61b72a2fc1",
    "_refresh_header_theme": "3d7f79b5b95654e10bdaff5e628851b717d34f1687bef39906dd3aac25368a2a",
    "_refresh_modern_shell_theme": "bc2b6f85d12771bd87a4acc294c10a94a5c6d913152b5454ca16228cf13cc4f7",
    "_theme_palette": "3fbc5f639f57dbeb38317f972b066ef4b341c34fdf0eec69e04a23e2339f9895",
    "_theme_toggle_text": "0b731a0168cf4cfc1dae0bc61be590016f430439967c231945b5ba54984446c5"
}

def _theme_toggle_text(self) -> str:
        # Button text shows the action (what you'll switch to)
        try:
            return "Light Mode" if getattr(self, "ui_theme", "light") == "dark" else "Dark Mode"
        except Exception:
            return "Dark Mode"

def _theme_palette(self, theme: str | None = None) -> dict:
        t = (theme or getattr(self, "ui_theme", "light") or "light").strip().lower()
        if t.startswith("d"):
            return {
                "bg": "#1f1f23",
                "panel": "#26262b",
                "header_bg": "#2a1b23",
                "fg": "#e9e9ef",
                "muted": "#b3b3bb",
                "border": "#3a3a42",
                "accent": "#ff86b9",
                "button_bg": "#32323a",
                "button_active": "#3c3c45",
                "entry_bg": "#2d2d34",
                "select_bg": "#3a3d46",
                "select_fg": "#ffffff",
                "tree_bg": "#26262b",
                "tree_sel_bg": "#3a3d46",
                "tree_sel_fg": "#ffffff",
                "heading_bg": "#2d2d34",
                "tab_bg": "#2d2d34",
                "tab_active_bg": "#353540",
                "tab_sel_bg": "#26262b",
            }
        # Light palette (current look)
        return {
            "bg": "#f7f7fb",
            "panel": "#ffffff",
            "header_bg": "#fff6f9",
            "fg": "#1a1a1a",
            "muted": "#666666",
            "border": "#dddddd",
            "accent": "#ffd1e6",
            "button_bg": "#ffffff",
            "button_active": "#ffd1e6",
            "entry_bg": "#ffffff",
            "select_bg": "#f3e6eb",
            "select_fg": "#2a1b23",
            "tree_bg": "#ffffff",
            "tree_sel_bg": "#f3e6eb",
            "tree_sel_fg": "#2a1b23",
            "heading_bg": "#ffffff",
            "tab_bg": "#ffffff",
            "tab_active_bg": "#fff0f7",
            "tab_sel_bg": "#ffffff",
        }

def _apply_ui_theme(self, style=None):
        # Configure ttk + tk colors based on self.ui_theme.
        p = self._theme_palette()
        self._ui_colors = p

        if style is None:
            try:
                style = ttk.Style(self.root)
            except Exception:
                style = None

        # Root background (helps around ttk areas)
        try:
            self.root.configure(bg=p["bg"])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0325', 'suppressed exception excpass_0325', __spina_exc)
            pass

        # Default options for plain tk widgets created later
        try:
            self.root.option_add("*Text.Background", p["entry_bg"])
            self.root.option_add("*Text.Foreground", p["fg"])
            self.root.option_add("*Text.InsertBackground", p["fg"])
            self.root.option_add("*Entry.Background", p["entry_bg"])
            self.root.option_add("*Entry.Foreground", p["fg"])
            self.root.option_add("*Entry.InsertBackground", p["fg"])
            self.root.option_add("*Listbox.Background", p["entry_bg"])
            self.root.option_add("*Listbox.Foreground", p["fg"])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0326', 'suppressed exception excpass_0326', __spina_exc)
            pass

        if style is None:
            return

        # Base surfaces
        try:
            style.configure("TFrame", background=p["bg"])
            style.configure("TLabel", background=p["bg"], foreground=p["fg"])
            style.configure("TLabelframe", background=p["bg"])
            style.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
            style.configure("AppShell.TFrame", background=p["bg"])
            style.configure("Sidebar.TFrame", background=p["panel"], relief="flat", borderwidth=0)
            style.configure("Content.TFrame", background=p["bg"], relief="flat", borderwidth=0)
            style.configure("Sidebar.TNotebook", background=p["bg"], borderwidth=0, tabmargins=0)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0327', 'suppressed exception excpass_0327', __spina_exc)
            pass

        # Header / accents
        try:
            style.configure("Pink.TFrame", background=p["header_bg"])
            style.configure("Pink.TLabel", background=p["header_bg"], foreground=p["fg"])
            style.configure("Preview.TFrame", background=p["panel"], relief="solid", borderwidth=1)
            style.configure("Toolbar.TFrame", background=p["bg"], padding=(10, 8))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0328', 'suppressed exception excpass_0328', __spina_exc)
            pass

        # Labels
        try:
            style.configure("Muted.TLabel", foreground=p["muted"])
            # Header/Section fonts are set in _setup_style; we keep colors consistent here.
            style.configure("Header.TLabel", background=p["bg"], foreground=p["fg"])
            style.configure("Section.TLabel", background=p["bg"], foreground=p["fg"])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0329', 'suppressed exception excpass_0329', __spina_exc)
            pass

        # Buttons
        try:
            style.configure("TButton", background=p["button_bg"], foreground=p["fg"])
            style.map("TButton",
                      background=[("active", p["button_active"]), ("pressed", p["button_active"])],
                      foreground=[("disabled", p["muted"])])
            style.configure("Primary.TButton", background=p["accent"], foreground="#1a1a1a")
            style.map("Primary.TButton", background=[("active", p["button_active"])])
            style.configure("Small.TButton", background=p["button_bg"], foreground=p["fg"])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0330', 'suppressed exception excpass_0330', __spina_exc)
            pass

        # Entries / Combobox
        try:
            style.configure("TEntry", fieldbackground=p["entry_bg"], background=p["entry_bg"], foreground=p["fg"])
            style.map("TEntry",
                      fieldbackground=[("disabled", p["bg"])],
                      foreground=[("disabled", p["muted"])])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0331', 'suppressed exception excpass_0331', __spina_exc)
            pass
        try:
            style.configure("TCombobox", fieldbackground=p["entry_bg"], background=p["entry_bg"], foreground=p["fg"])
            style.map("TCombobox",
                      fieldbackground=[("readonly", p["entry_bg"]), ("disabled", p["bg"])],
                      foreground=[("disabled", p["muted"])])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0332', 'suppressed exception excpass_0332', __spina_exc)
            pass

        # Notebook tabs
        try:
            style.configure("TNotebook", background=p["bg"], borderwidth=0)
            style.configure("TNotebook.Tab", background=p["tab_bg"], foreground=p["fg"])
            style.map("TNotebook.Tab",
                      background=[("selected", p["tab_sel_bg"]), ("active", p["tab_active_bg"])],
                      foreground=[("selected", p["fg"]), ("active", p["fg"])])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0333', 'suppressed exception excpass_0333', __spina_exc)
            pass

        # Treeview readability
        try:
            style.configure("Treeview",
                            background=p["tree_bg"],
                            fieldbackground=p["tree_bg"],
                            foreground=p["fg"],
                            bordercolor=p["border"],
                            rowheight=24,
                            relief="flat")
            style.map("Treeview",
                      background=[("selected", p["tree_sel_bg"])],
                      foreground=[("selected", p["tree_sel_fg"])])
            style.configure("Treeview.Heading",
                            background=p["heading_bg"],
                            foreground=p["fg"],
                            relief="flat")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0334', 'suppressed exception excpass_0334', __spina_exc)
            pass

        # Separator (minor)
        try:
            style.configure("TSeparator", background=p["border"])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0335', 'suppressed exception excpass_0335', __spina_exc)
            pass

        # Treeview zebra stripes (tags override style colors)
        try:
            self._apply_tree_stripes_all()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0336', 'suppressed exception excpass_0336', __spina_exc)
            pass

        # Apply to any already-created plain tk widgets
        try:
            self._apply_tk_theme_recursive(self.root)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0337', 'suppressed exception excpass_0337', __spina_exc)
            pass
        try:
            self._refresh_modern_shell_theme()
        except Exception:
            pass

def _apply_tk_theme_recursive(self, widget):
        # Best-effort theming for plain tk widgets (Text/Entry/etc.)
        try:
            p = getattr(self, "_ui_colors", None) or self._theme_palette()
        except Exception:
            p = self._theme_palette()

        try:
            cls = widget.winfo_class()
        except Exception:
            cls = ""

        try:
            if cls in ("Tk", "Toplevel"):
                widget.configure(bg=p["bg"])
            elif cls == "Frame":
                widget.configure(bg=p["bg"])
            elif cls == "Label":
                widget.configure(bg=p["bg"], fg=p["fg"])
            elif cls == "Entry":
                widget.configure(bg=p["entry_bg"], fg=p["fg"], insertbackground=p["fg"],
                                 disabledbackground=p["bg"], disabledforeground=p["muted"])
            elif cls == "Text":
                widget.configure(bg=p["entry_bg"], fg=p["fg"], insertbackground=p["fg"],
                                 selectbackground=p["select_bg"], selectforeground=p["select_fg"])
            elif cls == "Listbox":
                widget.configure(bg=p["entry_bg"], fg=p["fg"],
                                 selectbackground=p["select_bg"], selectforeground=p["select_fg"])
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0339', 'suppressed exception excpass_0339', __spina_exc)
            pass

        # Recurse
        try:
            for child in widget.winfo_children():
                self._apply_tk_theme_recursive(child)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0340', 'suppressed exception excpass_0340', __spina_exc)
            pass

def _refresh_modern_shell_theme(self):
        """Apply theme colors to the modern sidebar shell and rebuild nav labels/buttons."""
        try:
            p = getattr(self, '_ui_colors', None) or self._theme_palette()
            if getattr(self, 'main_shell', None) is not None:
                self.main_shell.configure(style='AppShell.TFrame')
            if getattr(self, 'sidebar_frame', None) is not None:
                self.sidebar_frame.configure(style='Sidebar.TFrame')
            if getattr(self, 'content_frame', None) is not None:
                self.content_frame.configure(style='Content.TFrame')
        except Exception as __spina_exc:
            _log_suppressed_once('modern_ui_pass_16039', 'modern UI shell style refresh skipped', __spina_exc)
            pass
        try:
            self._rebuild_side_nav()
        except Exception:
            try:
                self._refresh_side_nav_selection()
            except Exception as __spina_exc:
                _log_suppressed_once('modern_ui_pass_16046', 'modern UI shell sidebar selection fallback skipped', __spina_exc)
                pass

def _refresh_header_theme(self):
        """Apply the current theme colors to the modern top header."""
        hp = self._header_palette()
        try:
            if getattr(self, 'modern_header', None) is not None:
                self.modern_header.configure(bg=hp['bg'])
        except Exception as __spina_exc:
            _log_suppressed_once('modern_ui_pass_16194', 'modern UI header background refresh skipped', __spina_exc)
            pass
        for attr in ('header_left', 'header_center', 'header_right', 'mode_switch_frame'):
            try:
                w = getattr(self, attr, None)
                if w is not None:
                    w.configure(bg=hp['bg'] if attr != 'mode_switch_frame' else hp['panel'])
            except Exception as __spina_exc:
                _log_suppressed_once('modern_ui_pass_16201', 'modern UI header frame color refresh skipped', __spina_exc)
                pass
        for attr in ('header_title_label', 'header_view_title'):
            try:
                w = getattr(self, attr, None)
                if w is not None:
                    w.configure(bg=hp['bg'] if attr == 'header_title_label' else hp['panel'], fg=hp['fg'])
            except Exception as __spina_exc:
                _log_suppressed_once('modern_ui_pass_16208', 'modern UI header title color refresh skipped', __spina_exc)
                pass
        for attr in ('header_subtitle_label', 'mode_status_label'):
            try:
                w = getattr(self, attr, None)
                if w is not None:
                    w.configure(bg=hp['bg'] if attr == 'header_subtitle_label' else hp['panel'], fg=hp['muted'])
            except Exception:
                pass
        try:
            if getattr(self, 'pg_status_label', None) is not None:
                self.pg_status_label.configure(bg=hp['chip'], fg=hp['accent2'])
        except Exception:
            pass
        try:
            if getattr(self, 'theme_btn', None) is not None:
                self.theme_btn.configure(text=self._theme_toggle_text())
        except Exception:
            pass
        try:
            self._refresh_mode_toggle()
        except Exception:
            pass
