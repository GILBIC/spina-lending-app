from __future__ import annotations

import ast
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
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


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP_PATH))
    app_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    matches = [
        node for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    assert len(matches) == 1, f"Expected one legacy method, found {len(matches)}"
    method = matches[0]
    line_count = (method.end_lineno or method.lineno) - method.lineno + 1
    assert line_count == EXPECTED_LINES, line_count
    assert signature(method) == EXPECTED_SIGNATURE
    assert raw_sha(source, method) == EXPECTED_RAW_SHA256
    assert ast_sha(method) == EXPECTED_AST_SHA256

    bindings = []
    for node in tree.body:
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
    assert len(bindings) == 1
    assert ast.unparse(bindings[0].value) == EXPECTED_BINDING_VALUE

    direct_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == TARGET
    ]
    assert not direct_calls, f"Unexpected direct calls: {len(direct_calls)}"

    lines = source.splitlines(keepends=True)
    del lines[method.lineno - 1 : method.end_lineno]
    updated = "".join(lines)
    ast.parse(updated, filename=str(APP_PATH))
    APP_PATH.write_text(updated, encoding="utf-8")
    print(f"Removed {TARGET}: {line_count} guarded legacy lines")


if __name__ == "__main__":
    main()
