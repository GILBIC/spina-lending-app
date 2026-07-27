from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "audit_presentation.py"
TEST = ROOT / "tools" / "test_audit_presentation_wave_54.py"

TARGETS = ("_build_audit_tab", "refresh_audit_tab")
EXPECTED_LINES = {"_build_audit_tab": 70, "refresh_audit_tab": 113}
PROTECTED_CALLS = {
    "connect_db", "run_write", "execute", "executemany", "commit", "rollback",
    "backup", "restore", "renew_client", "add_transaction", "update_transaction",
    "delete_transaction", "generate_client_pdf", "generate_pdf_selected",
    "print_full_daily_ledger", "print_collector_route_daily_ledger",
    "print_databank_close_report", "save_users", "set_password", "authenticate",
}
FILESYSTEM_CALLS = {
    "open", "write", "write_text", "write_bytes", "unlink", "mkdir", "makedirs",
    "remove", "rename", "replace", "copy", "copy2", "move", "startfile", "Popen",
    "asksaveasfilename", "askopenfilename", "askdirectory",
}
FINANCIAL_NAMES = {
    "principal", "interest", "balance", "remaining_balance", "loan_amount",
    "daily_amount", "payment_amount", "total_payment", "offset_amount",
    "renewal_amount", "due_date", "advance_days", "pass_days", "variance",
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def identifier_names(node: ast.AST) -> set[str]:
    return {
        part.id.lower() for part in ast.walk(node) if isinstance(part, ast.Name)
    } | {
        part.attr.lower() for part in ast.walk(node) if isinstance(part, ast.Attribute)
    }


def assert_presentation_only(node: ast.FunctionDef) -> None:
    calls = {dotted(part.func).rsplit(".", 1)[-1] for part in ast.walk(node) if isinstance(part, ast.Call)}
    blocked = sorted((PROTECTED_CALLS | FILESYSTEM_CALLS) & calls)
    assert not blocked, (node.name, blocked)
    for part in ast.walk(node):
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            upper = part.value.upper()
            assert not any(token in upper for token in ("INSERT INTO", "DELETE FROM", "ALTER TABLE", "DROP TABLE", "CREATE TABLE")), (node.name, part.value)
        if isinstance(part, (ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.AugAssign)):
            hits = FINANCIAL_NAMES & identifier_names(part)
            assert not hits, (node.name, sorted(hits))


def direct_app_methods(tree: ast.Module) -> tuple[ast.ClassDef, dict[str, ast.FunctionDef]]:
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    methods = {
        node.name: node
        for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name in TARGETS
    }
    assert set(methods) == set(TARGETS), (set(TARGETS) - set(methods), set(methods))
    return app, methods


def build_module(method_sources: dict[str, str], metadata: dict[str, dict[str, object]]) -> str:
    protected = {
        "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
        "__name__", "__package__", "__spec__", "_AUDIT_PRESENTATION_DEPENDENCIES",
        "_PROTECTED_GLOBALS", "configure_audit_presentation_dependencies",
        "AUDIT_PRESENTATION_TARGETS", "AUDIT_PRESENTATION_SOURCE_LINES",
        "AUDIT_PRESENTATION_SOURCE_SHA256", "AUDIT_PRESENTATION_SIGNATURES",
        "AUDIT_PRESENTATION_CALLS", "AUDIT_PRESENTATION_TOTAL_SOURCE_LINES",
        *TARGETS,
    }
    blocks = [
        '"""Audit tab presentation extracted in Wave 54."""',
        "from __future__ import annotations",
        "",
        "_AUDIT_PRESENTATION_DEPENDENCIES = {}",
        f"_PROTECTED_GLOBALS = {protected!r}",
        "",
        "def configure_audit_presentation_dependencies(namespace):",
        "    _AUDIT_PRESENTATION_DEPENDENCIES.clear()",
        "    _AUDIT_PRESENTATION_DEPENDENCIES.update(namespace)",
        "    for name, value in namespace.items():",
        "        if name not in _PROTECTED_GLOBALS:",
        "            globals()[name] = value",
        "",
        f"AUDIT_PRESENTATION_TARGETS = {list(TARGETS)!r}",
        f"AUDIT_PRESENTATION_SOURCE_LINES = {{name: item['lines'] for name, item in {metadata!r}.items()}}",
        f"AUDIT_PRESENTATION_SOURCE_SHA256 = {{name: item['sha256'] for name, item in {metadata!r}.items()}}",
        f"AUDIT_PRESENTATION_SIGNATURES = {{name: item['signature'] for name, item in {metadata!r}.items()}}",
        f"AUDIT_PRESENTATION_CALLS = {{name: item['calls'] for name, item in {metadata!r}.items()}}",
        f"AUDIT_PRESENTATION_TOTAL_SOURCE_LINES = {sum(int(item['lines']) for item in metadata.values())}",
        "",
    ]
    for name in TARGETS:
        blocks.append(method_sources[name])
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def build_test(metadata: dict[str, dict[str, object]]) -> str:
    return f'''from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "audit_presentation.py"
TARGETS = {TARGETS!r}
EXPECTED = {metadata!r}


def normalized(source: str) -> str:
    return "\\n".join(line.rstrip() for line in source.strip().splitlines())


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{{left}}.{{node.attr}}" if left else node.attr
    return ""


def functions(tree: ast.AST, name: str):
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]


def main() -> None:
    module = importlib.import_module("spina_app.audit_presentation")
    assert module.AUDIT_PRESENTATION_TARGETS == list(TARGETS)
    assert module.AUDIT_PRESENTATION_TOTAL_SOURCE_LINES == 183
    assert module.AUDIT_PRESENTATION_SOURCE_LINES == {{name: item["lines"] for name, item in EXPECTED.items()}}
    assert module.AUDIT_PRESENTATION_SOURCE_SHA256 == {{name: item["sha256"] for name, item in EXPECTED.items()}}
    assert module.AUDIT_PRESENTATION_SIGNATURES == {{name: item["signature"] for name, item in EXPECTED.items()}}
    assert module.AUDIT_PRESENTATION_CALLS == {{name: item["calls"] for name, item in EXPECTED.items()}}

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text)
    for name in TARGETS:
        matches = [node for node in module_tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = "\\n".join(module_lines[node.lineno - 1 : node.end_lineno])
        assert len(normalized(source).splitlines()) == EXPECTED[name]["lines"]
        assert source_hash(source) == EXPECTED[name]["sha256"]
        assert ast.unparse(node.args) == EXPECTED[name]["signature"]
        calls = sorted({{dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)}})
        assert calls == EXPECTED[name]["calls"], (name, calls)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    app = next(node for node in desktop_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {{node.name for node in app.body if isinstance(node, ast.FunctionDef)}}
    assert not (set(TARGETS) & remaining), sorted(set(TARGETS) & remaining)

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.audit_presentation"
    ]
    assert len(imports) == 1
    aliases = {{(item.name, item.asname) for item in imports[0].names}}
    assert ("configure_audit_presentation_dependencies", "_wave54_configure_audit_presentation_dependencies") in aliases
    for name in TARGETS:
        assert (name, "_wave54" + name) in aliases

    configure = [
        node for node in desktop_tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_wave54_configure_audit_presentation_dependencies"
    ]
    assert len(configure) == 1

    bindings = []
    for node in desktop_tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
            and target.value.id == "App" and target.attr in TARGETS
            and isinstance(node.value, ast.Name)
        ):
            bindings.append((target.attr, node.value.id, node.lineno))
    assert sorted((name, value) for name, value, _ in bindings) == sorted((name, "_wave54" + name) for name in TARGETS)
    assert all(app.end_lineno < line for _, _, line in bindings)

    print("Wave 54 Audit presentation regression passed.")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(DESKTOP))
    app, methods = direct_app_methods(tree)

    method_sources: dict[str, str] = {}
    metadata: dict[str, dict[str, object]] = {}
    for name in TARGETS:
        node = methods[name]
        raw = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        source = textwrap.dedent(raw)
        actual_lines = len(normalized(source).splitlines())
        assert actual_lines == EXPECTED_LINES[name], (name, actual_lines, EXPECTED_LINES[name])
        assert_presentation_only(node)
        calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
        method_sources[name] = source
        metadata[name] = {
            "lines": actual_lines,
            "sha256": source_hash(source),
            "signature": ast.unparse(node.args),
            "calls": calls,
        }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == "App" and target.attr in TARGETS
            ):
                raise AssertionError(("existing App override", target.attr, node.lineno))

    edited = list(lines)
    removed = 0
    for node in sorted(methods.values(), key=lambda item: item.lineno, reverse=True):
        del edited[node.lineno - 1 : node.end_lineno]
        removed += node.end_lineno - node.lineno + 1

    new_app_end = app.end_lineno - removed
    wiring = [
        "",
        "# --- Wave 54 Audit presentation wiring ---",
        "from spina_app.audit_presentation import (",
        "    configure_audit_presentation_dependencies as _wave54_configure_audit_presentation_dependencies,",
        "    _build_audit_tab as _wave54_build_audit_tab,",
        "    refresh_audit_tab as _wave54refresh_audit_tab,",
        ")",
        "_wave54_configure_audit_presentation_dependencies(globals())",
        "App._build_audit_tab = _wave54_build_audit_tab",
        "App.refresh_audit_tab = _wave54refresh_audit_tab",
        "# --- End Wave 54 Audit presentation wiring ---",
        "",
    ]
    edited[new_app_end:new_app_end] = wiring

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(build_module(method_sources, metadata), encoding="utf-8")
    TEST.write_text(build_test(metadata), encoding="utf-8")
    DESKTOP.write_text("\n".join(edited) + "\n", encoding="utf-8")
    print("Extracted Audit presentation:", metadata)


if __name__ == "__main__":
    main()
