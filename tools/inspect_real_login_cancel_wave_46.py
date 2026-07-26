from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def contains_call(node: ast.AST, names: set[str]) -> bool:
    return any(isinstance(part, ast.Call) and dotted(part.func) in names for part in ast.walk(node))


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    init = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")

    interesting = []
    for stmt in init.body:
        if contains_call(stmt, {"self._prompt_login", "self._prompt_user_role", "self._destroy_root_safely"}):
            interesting.append(stmt)
        elif any(
            isinstance(part, ast.Attribute)
            and dotted(part) in {"self.mode_var", "self.current_user", "self.current_role", "self.user_role"}
            for part in ast.walk(stmt)
        ):
            interesting.append(stmt)

    print(f"App.__init__ lines: {init.lineno}-{init.end_lineno}")
    print("INTERESTING TOP-LEVEL STATEMENTS")
    for stmt in interesting:
        start = max(init.lineno, stmt.lineno - 8)
        end = min(init.end_lineno or stmt.end_lineno or stmt.lineno, (stmt.end_lineno or stmt.lineno) + 10)
        print(f"\n--- lines {start}-{end}; stmt {type(stmt).__name__} {stmt.lineno}-{stmt.end_lineno} ---")
        for number in range(start, end + 1):
            print(f"{number:05d}: {lines[number - 1]}")

    print("\nALL INIT BRANCHES WITH RETURN/RAISE/SAFE DESTROY")
    for node in ast.walk(init):
        if not isinstance(node, ast.If):
            continue
        if not (
            contains_call(node, {"self._destroy_root_safely", "self._prompt_login", "self._prompt_user_role"})
            or any(isinstance(part, (ast.Return, ast.Raise)) for part in ast.walk(node))
        ):
            continue
        source = ast.get_source_segment(text, node) or ""
        print(f"\n--- If lines {node.lineno}-{node.end_lineno} ---")
        print(source[:4000])


if __name__ == "__main__":
    main()
