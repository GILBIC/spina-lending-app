from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "area_hierarchy_ui.py"
OUTPUT_PATH = ROOT / "docs" / "wave71-area-manager-meta.json"

TARGET = "open_areas_manager"
EXPECTED_LINES = 162
EXPECTED_SIGNATURE = "self"
EXPECTED_RAW_SHA256 = "2b17e8a26daecce5f0d4a8098939c4bf2cf3fdc7be803a5e54faf0ff94c6d551"
EXPECTED_AST_SHA256 = "7b8f145e8698706cfa6a986d535d23cb2b054be42b509d98328b2b654ba2be22"
EXPECTED_BINDING_VALUE = "_spina_area_open_manager"


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
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


def ast_sha(node: ast.AST) -> str:
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def raw_sha(source: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(source, node) or ""
    return hashlib.sha256(segment.encode("utf-8")).hexdigest()


def is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "main"
        for child in ast.walk(node)
    )


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    module_source = MODULE_PATH.read_text(encoding="utf-8")
    app_tree = ast.parse(app_source, filename=str(APP_PATH))
    module_tree = ast.parse(module_source, filename=str(MODULE_PATH))

    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    legacy_matches = [
        node for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    assert len(legacy_matches) == 1, f"Expected one legacy method, found {len(legacy_matches)}"
    legacy = legacy_matches[0]
    line_count = (legacy.end_lineno or legacy.lineno) - legacy.lineno + 1
    assert line_count == EXPECTED_LINES, line_count
    assert signature(legacy) == EXPECTED_SIGNATURE
    assert raw_sha(app_source, legacy) == EXPECTED_RAW_SHA256
    assert ast_sha(legacy) == EXPECTED_AST_SHA256

    bindings: list[ast.Assign] = []
    for node in app_tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
                and target.attr == TARGET
            ):
                bindings.append(node)
    assert len(bindings) == 1, f"Expected one active binding, found {len(bindings)}"
    assert ast.unparse(bindings[0].value) == EXPECTED_BINDING_VALUE

    final_guards = [node for node in app_tree.body if is_main_guard(node)]
    assert final_guards, "Final main guard not found"
    assert bindings[0].lineno < max(final_guards, key=lambda node: node.lineno).lineno

    app_method_calls = [
        node for node in ast.walk(app_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == TARGET
    ]
    assert not app_method_calls, f"Unexpected direct legacy calls: {len(app_method_calls)}"

    modern_matches = [
        node for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "open_area_manager"
    ]
    assert len(modern_matches) == 1, f"Expected one modern manager, found {len(modern_matches)}"
    modern = modern_matches[0]
    modern_calls = [
        node for node in ast.walk(module_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open_area_manager"
    ]
    assert len(modern_calls) >= 2, f"Expected modern selector calls, found {len(modern_calls)}"

    report = {
        "legacy_method": f"App.{TARGET}",
        "legacy_start_line": legacy.lineno,
        "legacy_end_line": legacy.end_lineno,
        "legacy_line_count": line_count,
        "legacy_signature": signature(legacy),
        "legacy_raw_sha256": raw_sha(app_source, legacy),
        "legacy_ast_sha256": ast_sha(legacy),
        "direct_legacy_call_count": len(app_method_calls),
        "binding_line": bindings[0].lineno,
        "binding_value": ast.unparse(bindings[0].value),
        "modern_module": str(MODULE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "modern_function": "open_area_manager",
        "modern_signature": signature(modern),
        "modern_start_line": modern.lineno,
        "modern_end_line": modern.end_lineno,
        "modern_line_count": (modern.end_lineno or modern.lineno) - modern.lineno + 1,
        "modern_ast_sha256": ast_sha(modern),
        "modern_direct_call_count": len(modern_calls),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
