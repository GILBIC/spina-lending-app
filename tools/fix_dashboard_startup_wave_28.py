"""Guarded repair for Wave 28 Dashboard startup import ordering."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TEST = ROOT / "tools" / "test_dashboard_presentation_wave_28.py"

EXPECTED_SOURCE_BLOB = "944fba3147dc27cd052fe1b5d2284c9d143fcf5c"
EXPECTED_TEST_BLOB = "4394e419ac9423e65f7a8a898f3b8abe86e4540f"

TARGETS = (
    "_spina_dashboard_summary_text",
    "_spina_configure_dashboard_tree_theme",
    "_spina_build_dashboard_tab",
    "_spina_populate_dashboard_tree",
    "_spina_refresh_dashboard",
    "_spina_apply_dashboard_role",
    "_spina_v18_patch_dashboard_chart_cards",
    "_spina_v18_populate_dashboard_tree",
    "_spina_v18_refresh_dashboard",
    "_spina_v19_populate_dashboard_tree",
    "_spina_v19_refresh_dashboard",
    "_spina_v20_populate_dashboard_tree",
    "_spina_v20_refresh_dashboard",
)


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], cwd=ROOT, text=True
    ).strip()


def function_hashes(text: str) -> dict[str, str]:
    tree = ast.parse(text)
    lines = text.splitlines()
    result: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            result[node.name] = hashlib.sha256(segment.encode("utf-8")).hexdigest()
    return result


def render_import(node: ast.ImportFrom, aliases: list[ast.alias]) -> str:
    if not aliases:
        return ""
    rendered = []
    for alias in aliases:
        rendered.append(
            f"    {alias.name} as {alias.asname}," if alias.asname else f"    {alias.name},"
        )
    return f"from {node.module} import (\n" + "\n".join(rendered) + "\n)\n"


def replacement_lines(value: str) -> list[str]:
    if value and not value.endswith("\n"):
        value += "\n"
    return value.splitlines(keepends=True)


def apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    lines = text.splitlines(keepends=True)
    for start, end, value in sorted(edits, key=lambda item: item[0], reverse=True):
        lines[start:end] = replacement_lines(value)
    return "".join(lines)


def top_level_runtime_uses(tree: ast.Module) -> list[tuple[int, ast.stmt, set[str]]]:
    target_set = set(TARGETS)
    found: list[tuple[int, ast.stmt, set[str]]] = []
    ignored = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Import,
        ast.ImportFrom,
    )
    for statement in tree.body:
        if isinstance(statement, ignored):
            continue
        names = {
            node.id
            for node in ast.walk(statement)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in target_set
        }
        if names:
            found.append((statement.lineno, statement, names))
    return found


def build_early_import() -> str:
    body = "\n".join(f"    {name}," for name in TARGETS)
    return (
        "# Wave 28 Dashboard helpers must be imported before App monkey-patch wiring.\n"
        "from spina_app.tabs.dashboard import (\n"
        f"{body}\n"
        ")\n\n"
    )


def patch_test(text: str) -> str:
    helper_marker = "\n\ndef main() -> None:\n"
    assert text.count(helper_marker) == 1, "Wave 28 test main marker changed"
    helpers = '''


def assert_dashboard_startup_wiring() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(SOURCE))
    target_names = set(EXPECTED_HASHES)

    complete_imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard":
            names = {alias.asname or alias.name for alias in node.names}
            if target_names.issubset(names):
                complete_imports.append(node)
    assert len(complete_imports) == 1, "Expected one complete Wave 28 Dashboard import"
    import_line = complete_imports[0].lineno

    runtime_uses = []
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            continue
        names = {
            node.id
            for node in ast.walk(statement)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in target_names
        }
        if names:
            runtime_uses.append((statement.lineno, names))
    assert runtime_uses, "No Dashboard App wiring use found"
    first_use_line = min(line for line, _ in runtime_uses)
    assert import_line < first_use_line, (import_line, first_use_line, runtime_uses[:3])


class FakeNotebook:
    def __init__(self):
        self.visible = [".!data"]
        self.hidden = []

    def tabs(self):
        return tuple(self.visible)

    def insert(self, index, tab, text=""):
        value = str(tab)
        if value not in self.visible:
            self.visible.insert(min(int(index), len(self.visible)), value)

    def add(self, tab, text=""):
        value = str(tab)
        if value not in self.visible:
            self.visible.append(value)

    def hide(self, tab):
        value = str(tab)
        self.hidden.append(value)
        if value in self.visible:
            self.visible.remove(value)


def assert_dashboard_role_visibility() -> None:
    class RoleApp:
        pass

    app = RoleApp()
    app.nb = FakeNotebook()
    app.tab_dashboard = ".!dashboard"
    app.user_role = "Admin"
    dashboard._spina_apply_dashboard_role(app)
    assert str(app.tab_dashboard) in app.nb.tabs(), "Admin Dashboard was not inserted"

    app.user_role = "System"
    dashboard._spina_apply_dashboard_role(app)
    assert str(app.tab_dashboard) not in app.nb.tabs(), "System Dashboard was not hidden"
    assert str(app.tab_dashboard) in app.nb.hidden
'''
    text = text.replace(helper_marker, helpers + helper_marker)

    old_calls = '''    # Defensive UI helpers must stay no-throw when optional widgets are absent.
    dashboard._spina_configure_dashboard_tree_theme(EmptyApp())
    dashboard._spina_apply_dashboard_role(EmptyApp())

    print("Dashboard presentation Wave 28 regression passed:", len(EXPECTED_HASHES), "functions,", total_lines, "lines")
'''
    new_calls = '''    # Defensive UI helpers must stay no-throw when optional widgets are absent.
    dashboard._spina_configure_dashboard_tree_theme(EmptyApp())
    dashboard._spina_apply_dashboard_role(EmptyApp())

    assert_dashboard_startup_wiring()
    assert_dashboard_role_visibility()

    print("Dashboard presentation Wave 28 regression passed:", len(EXPECTED_HASHES), "functions,", total_lines, "lines")
'''
    assert text.count(old_calls) == 1, "Wave 28 test call block changed"
    return text.replace(old_calls, new_calls)


def main() -> None:
    assert git_blob(SOURCE) == EXPECTED_SOURCE_BLOB, (
        git_blob(SOURCE),
        EXPECTED_SOURCE_BLOB,
    )
    assert git_blob(TEST) == EXPECTED_TEST_BLOB, (git_blob(TEST), EXPECTED_TEST_BLOB)

    source_text = SOURCE.read_text(encoding="utf-8")
    original_hashes = function_hashes(source_text)
    tree = ast.parse(source_text, filename=str(SOURCE))

    dashboard_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.tabs.dashboard"
    ]
    assert dashboard_imports, "Dashboard imports are missing"

    target_set = set(TARGETS)
    imported_targets = {
        alias.name
        for node in dashboard_imports
        for alias in node.names
        if alias.name in target_set
    }
    assert imported_targets == target_set, sorted(target_set - imported_targets)

    runtime_uses = top_level_runtime_uses(tree)
    assert runtime_uses, "Dashboard App wiring use is missing"
    first_use_line, first_use_node, first_use_names = min(runtime_uses, key=lambda item: item[0])

    target_import_lines = [
        node.lineno
        for node in dashboard_imports
        if any(alias.name in target_set for alias in node.names)
    ]
    assert min(target_import_lines) > first_use_line, (
        "Dashboard startup ordering is already different",
        target_import_lines,
        first_use_line,
        sorted(first_use_names),
    )

    edits: list[tuple[int, int, str]] = []
    for node in dashboard_imports:
        remaining = [alias for alias in node.names if alias.name not in target_set]
        if len(remaining) != len(node.names):
            edits.append((node.lineno - 1, node.end_lineno, render_import(node, remaining)))

    edits.append((first_use_node.lineno - 1, first_use_node.lineno - 1, build_early_import()))
    new_source = apply_edits(source_text, edits)
    ast.parse(new_source, filename=str(SOURCE))
    assert function_hashes(new_source) == original_hashes, "A desktop function body changed"

    new_tree = ast.parse(new_source)
    complete_imports = []
    for node in new_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard":
            names = {alias.name for alias in node.names}
            if target_set.issubset(names):
                complete_imports.append(node)
    assert len(complete_imports) == 1
    assert complete_imports[0].lineno < first_use_line

    SOURCE.write_text(new_source, encoding="utf-8")
    TEST.write_text(patch_test(TEST.read_text(encoding="utf-8")), encoding="utf-8")

    print(
        "Dashboard startup wiring repaired:",
        len(TARGETS),
        "imports moved before line",
        first_use_line,
    )


if __name__ == "__main__":
    main()
