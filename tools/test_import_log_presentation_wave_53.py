from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "import_log_presentation.py"
TARGET = "_show_import_log_window"
ALIAS = "_wave53_show_import_log_window"
CONFIG_ALIAS = "_configure_wave53_import_log"
EXPECTED_LINES = 337
EXPECTED_SHA256 = "017ec81edcd4d086f905ce5a147a0a0855073f354ed63955d171aa15ed22c912"
SQL_RE = re.compile(
    r"(?:\bSELECT\b[\s\S]{0,120}\bFROM\b|\bINSERT\s+INTO\b|\bUPDATE\b[\s\S]{0,80}\bSET\b|"
    r"\bDELETE\s+FROM\b|\bALTER\s+TABLE\b|\bDROP\s+TABLE\b|\bCREATE\s+TABLE\b)",
    re.I,
)
PROTECTED_IDENTIFIERS = {
    "connect_db", "cursor", "execute", "executemany", "commit", "rollback", "run_write",
    "principal", "interest", "interest_rate", "interest_amount", "balance", "renewal",
    "offset", "advance", "adv", "due_date", "daily_amount", "loan_amount", "payment_term",
    "flex_due", "close_day", "delete_day", "verify_login", "hash_password",
    "set_user_password", "apply_role_access", "switch_account",
}


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in textwrap.dedent(source).strip().splitlines()) + "\n"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def desktop_callers(tree: ast.Module) -> tuple[str, ...]:
    names: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            for child in node.body:
                self.visit(child)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr == TARGET:
                names.add(".".join(self.stack) or "<module>")
            self.generic_visit(node)

    Visitor().visit(tree)
    return tuple(sorted(names))


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)

    app_classes = [node for node in desktop_tree.body if isinstance(node, ast.ClassDef) and node.name == "App"]
    assert len(app_classes) == 1
    assert not [node for node in app_classes[0].body if isinstance(node, ast.FunctionDef) and node.name == TARGET]

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.import_log_presentation"
    ]
    assert len(imports) == 1
    aliases = {(alias.name, alias.asname) for alias in imports[0].names}
    assert ("configure_import_log_dependencies", CONFIG_ALIAS) in aliases
    assert (TARGET, ALIAS) in aliases

    configs = [
        node for node in desktop_tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == CONFIG_ALIAS
    ]
    assert len(configs) == 1

    bindings = [
        node for node in desktop_tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Attribute)
        and isinstance(node.targets[0].value, ast.Name)
        and node.targets[0].value.id == "App"
        and node.targets[0].attr == TARGET
        and isinstance(node.value, ast.Name)
    ]
    assert len(bindings) == 1
    assert bindings[0].value.id == ALIAS

    main_guards = [
        node for node in desktop_tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    assert main_guards
    assert imports[0].lineno < bindings[0].lineno < main_guards[-1].lineno
    assert configs[0].lineno < bindings[0].lineno

    defs = [node for node in module_tree.body if isinstance(node, ast.FunctionDef) and node.name == TARGET]
    assert len(defs) == 1
    source = ast.get_source_segment(module_text, defs[0])
    assert source is not None
    assert len(source.splitlines()) == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256

    module = importlib.import_module("spina_app.import_log_presentation")
    assert module.IMPORT_LOG_TARGET == TARGET
    assert module.IMPORT_LOG_SOURCE_LINES == EXPECTED_LINES
    assert module.IMPORT_LOG_SOURCE_SHA256 == EXPECTED_SHA256
    assert tuple(module.IMPORT_LOG_CALLERS) == desktop_callers(desktop_tree)
    assert module.IMPORT_LOG_CALLERS

    sig = inspect.signature(module._show_import_log_window)
    assert list(sig.parameters) == ["self", "title", "summary", "lines", "default_save_path"]

    calls = {dotted(node.func) for node in ast.walk(defs[0]) if isinstance(node, ast.Call)}
    identifiers = {
        node.id.lower() for node in ast.walk(defs[0]) if isinstance(node, ast.Name)
    } | {
        node.attr.lower() for node in ast.walk(defs[0]) if isinstance(node, ast.Attribute)
    }
    assert not any(call.startswith("self.db") or call.startswith("db.") for call in calls)
    assert not (identifiers & {name.lower() for name in PROTECTED_IDENTIFIERS})
    for node in ast.walk(defs[0]):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_RE.search(node.value)

    assert "filedialog.asksaveasfilename" in calls
    assert "win.clipboard_append" in calls
    assert "_open_path" in calls
    assert "open" in calls
    assert "os.makedirs" in calls

    print(
        "Wave 53 Import Log presentation regression passed: "
        f"{EXPECTED_LINES} exact lines, callers={module.IMPORT_LOG_CALLERS}."
    )


if __name__ == "__main__":
    main()
