from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
SOURCE_OUT = ROOT / "docs" / "wave69-collector-editor-source.txt"
META_OUT = ROOT / "docs" / "wave69-collector-editor-meta.json"
TARGET = "_collector_editor_dialog"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    pieces: list[str] = []
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f"={ast.unparse(default)}"
        pieces.append(text)
    if node.args.vararg:
        pieces.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        pieces.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f"={ast.unparse(default)}"
        pieces.append(text)
    if node.args.kwarg:
        pieces.append(f"**{node.args.kwarg.arg}")
    return ", ".join(pieces)


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    app_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    method = next(
        node for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    )
    start = method.lineno - 1
    end = method.end_lineno
    source = "".join(lines[start:end])

    calls = sorted({
        dotted(node.func)
        for node in ast.walk(method)
        if isinstance(node, ast.Call) and dotted(node.func)
    })
    db_calls = [name for name in calls if name.startswith("self.db.")]
    self_calls = [name for name in calls if name.startswith("self.")]
    names_loaded = sorted({
        node.id for node in ast.walk(method)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    })

    metadata = {
        "target": TARGET,
        "start_line": method.lineno,
        "end_line": method.end_lineno,
        "lines": method.end_lineno - method.lineno + 1,
        "signature": signature(method),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "calls": calls,
        "self_calls": self_calls,
        "db_calls": db_calls,
        "names_loaded": names_loaded,
    }
    SOURCE_OUT.write_text(source, encoding="utf-8")
    META_OUT.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
