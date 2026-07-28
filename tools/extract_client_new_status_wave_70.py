from __future__ import annotations

import ast
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "client_new_status.py"
TARGET = "_is_client_new"
EXPECTED_LINES = 124
EXPECTED_SIGNATURE = "self, name, ledger_date, days=None"
EXPECTED_RAW_SHA256 = "8a9776860733a1df8a2630761c058a6cdca28b1f7db52a16e52ae24e0b9b4b03"
EXPECTED_AST_SHA256 = "8126404f3be36835e43194271e130c4e3477512e2871e5fa5b313753fd4629c1"
BINDING_BLOCK = """# Wave 70: read-only client NEW-status calculation.\nfrom spina_app.client_new_status import (\n    configure_client_new_status_dependencies as _configure_wave70_client_new,\n    _is_client_new as _wave70_is_client_new,\n)\n_configure_wave70_client_new(globals())\nApp._is_client_new = _wave70_is_client_new\n\n\n"""
FINAL_MAIN_MARKER = "if __name__ == '__main__':\n    main()"


def signature(node: ast.FunctionDef) -> str:
    parts: list[str] = []
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if default is not None:
            text += f"={ast.unparse(default)}"
        parts.append(text)
    if node.args.vararg:
        parts.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if default is not None:
            text += f"={ast.unparse(default)}"
        parts.append(text)
    if node.args.kwarg:
        parts.append(f"**{node.args.kwarg.arg}")
    return ", ".join(parts)


def function_ast_hash(path: Path, function_name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    assert len(matches) == 1, f"Expected one {function_name} in {path}, found {len(matches)}"
    normalized = ast.dump(matches[0], annotate_fields=True, include_attributes=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    assert BINDING_BLOCK not in text, "Wave 70 binding already exists"
    tree = ast.parse(text, filename=str(APP_PATH))
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    matches = [node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == TARGET]
    assert len(matches) == 1, f"Expected one App.{TARGET}, found {len(matches)}"
    node = matches[0]
    start = node.lineno
    end = node.end_lineno or start
    assert end - start + 1 == EXPECTED_LINES
    assert signature(node) == EXPECTED_SIGNATURE

    lines = text.splitlines(keepends=True)
    source = "".join(lines[start - 1:end])
    assert hashlib.sha256(source.encode("utf-8")).hexdigest() == EXPECTED_RAW_SHA256
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    assert hashlib.sha256(normalized.encode("utf-8")).hexdigest() == EXPECTED_AST_SHA256
    assert function_ast_hash(MODULE_PATH, TARGET) == EXPECTED_AST_SHA256

    callers = [
        child for child in ast.walk(tree)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == TARGET
    ]
    assert len(callers) == 4, f"Expected four live callers, found {len(callers)}"

    without_method = "".join(lines[:start - 1] + lines[end:])
    marker_at = without_method.rfind(FINAL_MAIN_MARKER)
    assert marker_at >= 0, "Final main guard not found"
    updated = without_method[:marker_at] + BINDING_BLOCK + without_method[marker_at:]

    updated_tree = ast.parse(updated, filename=str(APP_PATH))
    updated_app = next(node for node in updated_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    assert not [
        child for child in updated_app.body
        if isinstance(child, ast.FunctionDef) and child.name == TARGET
    ]
    assert updated.count("App._is_client_new = _wave70_is_client_new") == 1
    assert updated.count("_configure_wave70_client_new(globals())") == 1

    APP_PATH.write_text(updated, encoding="utf-8")
    print(
        f"Extracted App.{TARGET}: {EXPECTED_LINES} lines, "
        f"raw={EXPECTED_RAW_SHA256}, ast={EXPECTED_AST_SHA256}"
    )


if __name__ == "__main__":
    main()
