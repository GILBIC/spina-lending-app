"""Focused regression checks for Navigation + Data Bank shell Wave 29."""

from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

from spina_app import navigation
from spina_app.tabs import data_bank_shell

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
NAV_MODULE = ROOT / "spina_app" / "navigation.py"
DATA_MODULE = ROOT / "spina_app" / "tabs" / "data_bank_shell.py"

GROUPS = {
    "navigation": {
        "_update_data_toolbar": "1af8b42b2ee75d4f77895c3967aeeae7da2f52ca252802d4d998a30037af27d8",
        "_side_nav_items": "2292ae8c5f0abfb3377e87f3806b3b4fdb60044c9d87d12870058c46f3070992",
        "_rebuild_side_nav": "21038d8e472cb203ef8d97bb7ca046ba1f0aa5747c50b4bb8e93fbc8e8f321ac",
        "_refresh_side_nav_selection": "267a6a9c6b03e86e0bb5a7e8f12d6ba30d45f671aeca5b5768e043e304265b7f",
        "_header_palette": "95fe45cc646eb065f154c094f0ff0c3a0ca3d0daedd9912f431df04e91b6ea6a",
        "_make_header_button": "3e459cc3abb6a0a9e75d6579c16ceed914bf132a5ccbce1068189848bc363ec3",
        "_refresh_mode_toggle": "59fcb7a113e603b46a57c4a4104df994117ec007ef5f7980e6337ce62e2ee91c",
        "_vscroll": "48efe34b1cd4c5c71242b0ff1a804abb1804ee43d2c483851226d2ae4f3394f1",
        "_month_label": "28a2bef3865fa0cd2f818b97b33b2f885b967b5f7ea0d9cb83f744a8bced412a",
        "_on_mousewheel_sync": "7258e548972db5e497e1177b9bedc778822ebe924afde5f4935afcc278e16dc6",
        "_update_toolbar_states": "bd423a3ffc8b56588c4816137f4a9f5180da3767ee947f8b164de4283bf542bd",
    },
    "data_bank_shell": {
        "_looks_like_data_grid": "c46f3d5b5f3363d46352d1dc690a075820f59a62d21969d134054557a747b6ff",
        "_locate_data_tree": "355c3a1b8445ce76e1fd939447b00766d881feed1a2903035a5882a31266d0a5",
        "_ensure_databank_edit_bindings": "afc7b403055a870249ef2aeca67d8d2e32b29960a97787fdb01307ef5aeafe9b",
        "_show_audit_tab": "b9c0a43f780b524fba160c1fb6b83feab1c5b82a3d772a1e54598b967767a18f",
        "_hide_audit_tab": "ae19be5e52cef380acf5b7148668a5f8561076b926cdea35be5841fd42d5d5eb",
        "_resize_databank_columns": "d350345101372a9246ffeb133be9c8b201adb72b123d95167656ddd3f0c0f927",
    },
}
EXPECTED_LINES = 546
ALL_TARGETS = {name for group in GROUPS.values() for name in group}


def top_level_functions(path: Path) -> dict[str, tuple[ast.AST, str]]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    lines = text.splitlines()
    return {
        node.name: (node, "\n".join(lines[node.lineno - 1 : node.end_lineno]))
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def assert_exact_method_bodies() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    source_tree = ast.parse(source_text, filename=str(SOURCE))
    app = next(node for node in source_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {
        node.name
        for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not (ALL_TARGETS & remaining), sorted(ALL_TARGETS & remaining)

    total_lines = 0
    for group, path in (("navigation", NAV_MODULE), ("data_bank_shell", DATA_MODULE)):
        functions = top_level_functions(path)
        assert set(GROUPS[group]).issubset(functions), sorted(set(GROUPS[group]) - set(functions))
        for name, expected_hash in GROUPS[group].items():
            node, source = functions[name]
            reconstructed = textwrap.indent(source, "    ")
            actual_hash = hashlib.sha256(reconstructed.encode("utf-8")).hexdigest()
            assert actual_hash == expected_hash, (name, actual_hash, expected_hash)
            total_lines += (node.end_lineno or node.lineno) - node.lineno + 1
    assert total_lines == EXPECTED_LINES, total_lines


def assignment_rows(tree: ast.Module) -> dict[str, list[tuple[int, str]]]:
    result = {name: [] for name in ALL_TARGETS}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
                and target.attr in result
            ):
                value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
                result[target.attr].append((node.lineno, ast.unparse(value)))
    return result


def assert_startup_wiring() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(SOURCE))
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    main_guards = [
        node.lineno
        for node in tree.body
        if isinstance(node, ast.If)
        and "__name__" in ast.unparse(node.test)
        and "__main__" in ast.unparse(node.test)
    ]
    assert main_guards
    final_launch = max(main_guards)
    rows = assignment_rows(tree)
    for name, assignments in rows.items():
        wave29 = [row for row in assignments if "_wave29_" in row[1]]
        assert len(wave29) == 1, (name, assignments)
        line, _ = wave29[0]
        assert app.end_lineno < line < final_launch, (name, app.end_lineno, line, final_launch)

    # Preserve the historical late override; it must still win at runtime.
    toolbar_rows = rows["_update_data_toolbar"]
    wave29_line = next(line for line, rhs in toolbar_rows if "_wave29_" in rhs)
    later = [(line, rhs) for line, rhs in toolbar_rows if line > wave29_line]
    assert later, toolbar_rows
    assert all("_wave29_" not in rhs for _, rhs in later), later

    imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module in {"spina_app.navigation", "spina_app.tabs.data_bank_shell"}
    ]
    assert len(imports) == 2, [(node.module, node.lineno) for node in imports]
    assert all(app.end_lineno < node.lineno < final_launch for node in imports)


class FakeNotebook:
    def __init__(self, tabs):
        self._tabs = list(tabs)
        self.added = []
        self.hidden = []

    def tabs(self):
        return tuple(str(tab) for tab in self._tabs)

    def tab(self, tab, option=None, **kwargs):
        if kwargs:
            return None
        return "normal"

    def add(self, tab, text=""):
        self.added.append((tab, text))
        if tab not in self._tabs:
            self._tabs.append(tab)

    def hide(self, tab):
        self.hidden.append(tab)
        if tab in self._tabs:
            self._tabs.remove(tab)


class FakeTree:
    def __init__(self, columns=()):
        self.columns = tuple(columns)
        self.bindings = []
        self.scrolls = []
        self._edit_bindings_done = False

    def __getitem__(self, key):
        if key == "columns":
            return self.columns
        raise KeyError(key)

    def heading(self, column):
        text = str(column)[1:] if str(column).startswith("d") else str(column)
        return {"text": text}

    def winfo_class(self):
        return "Treeview"

    def bind(self, event, callback, add=None):
        self.bindings.append((event, callback, add))

    def yview_scroll(self, amount, units):
        self.scrolls.append((amount, units))


class FakeVar:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class FakeButton:
    def __init__(self):
        self.options = {}

    def config(self, **kwargs):
        self.options.update(kwargs)

    configure = config


def assert_navigation_behavior() -> None:
    logs = []
    navigation.configure_navigation_dependencies(
        log_suppressed_once=lambda *args, **kwargs: logs.append((args, kwargs)),
        fmt_currency_callback=lambda value: f"MONEY:{float(value):.2f}",
    )

    class App:
        grid_month = 7
        grid_year = 2026
        ui_theme = "light"

        def _theme_palette(self):
            return {}

    app = App()
    assert navigation._month_label(app) == "July 2026"
    assert navigation._header_palette(app)["panel"] == "#ffffff"
    app.ui_theme = "dark"
    assert navigation._header_palette(app)["panel"] == "#1f2028"

    app.tab_data = ".data"
    app.tab_reports = ".reports"
    app.tab_clients = None
    app.tab_collectors = None
    app.tab_audit = None
    app.tab_system_data = None
    app.nb = FakeNotebook([app.tab_data, app.tab_reports])
    items = navigation._side_nav_items(app)
    assert [(title, icon) for _, title, icon in items] == [("Data Bank", "▦"), ("Reports", "▤")]

    app.name_tree = FakeTree()
    app.days_tree = FakeTree()
    event = type("Event", (), {"delta": -120, "num": None})()
    assert navigation._on_mousewheel_sync(app, event) == "break"
    assert app.name_tree.scrolls == [(1, "units")]
    assert app.days_tree.scrolls == [(1, "units")]

    app._del_client_btn = FakeButton()
    app.clients_tree = type("SelectionTree", (), {"selection": lambda self: ("row",)})()
    navigation._update_toolbar_states(app)
    assert app._del_client_btn.options["state"] == "normal"

    app._db_close_info_var = FakeVar()
    app._get_databank_focus_date = lambda: "2026-07-25"
    app.db = type(
        "DB",
        (),
        {
            "get_databank_day_close": lambda self, date: {
                "variance": 12.5,
                "is_closed": 1,
                "variance_status": "Short",
                "variance_workflow_status": "Open",
            }
        },
    )()
    navigation._update_data_toolbar(app)
    assert "CLOSED" in app._db_close_info_var.value
    assert "MONEY:12.50" in app._db_close_info_var.value



def assert_data_bank_shell_behavior() -> None:
    ignored = []
    data_bank_shell.configure_data_bank_shell_dependencies(
        log_suppressed_once=lambda *args, **kwargs: None,
        log_ignored=lambda *args, **kwargs: ignored.append((args, kwargs)),
    )

    columns = ("client", "area", *tuple(f"d{day}" for day in range(1, 13)))
    tree = FakeTree(columns)
    app = type("App", (), {})()
    assert data_bank_shell._looks_like_data_grid(app, tree) is True

    app.days_tree = tree
    app.root = object()
    app._walk_widgets = lambda root: []
    app._looks_like_data_grid = lambda widget: True
    assert data_bank_shell._locate_data_tree(app) is tree

    app._locate_data_tree = lambda: tree
    app._begin_cell_edit = object()
    app._remember_cell_click = object()
    app.delete_selected_cell = object()
    app._on_mousewheel_sync = object()
    data_bank_shell._ensure_databank_edit_bindings(app)
    events = [event for event, _, _ in tree.bindings]
    assert events == ["<Double-1>", "<F2>", "<Button-1>", "<Delete>", "<MouseWheel>", "<Button-4>", "<Button-5>"]
    assert tree._edit_bindings_done is True

    app.tab_audit = ".audit"
    app.nb = FakeNotebook([])
    data_bank_shell._show_audit_tab(app)
    assert app.nb.added == [(".audit", "Audit")]
    data_bank_shell._hide_audit_tab(app)
    assert app.nb.hidden == [".audit"]

    # Defensive layout helper stays no-throw when the right grid is not available.
    app.days_tree = None
    data_bank_shell._resize_databank_columns(app)


def main() -> None:
    assert_exact_method_bodies()
    assert_startup_wiring()
    assert_navigation_behavior()
    assert_data_bank_shell_behavior()
    print("Navigation + Data Bank shell Wave 29 regression passed: 17 methods, 546 lines")


if __name__ == "__main__":
    main()
