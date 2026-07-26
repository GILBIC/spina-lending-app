from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TEST = ROOT / "tools/test_login_cancel_startup_wave_46.py"


def dotted(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def has_call(node: ast.AST, target: str) -> bool:
    return any(isinstance(part, ast.Call) and dotted(part.func) == target for part in ast.walk(node))


def find_login_try(tree: ast.Module) -> ast.Try:
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    init = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    matches = []
    for node in ast.walk(init):
        if not isinstance(node, ast.Try):
            continue
        if not any(has_call(stmt, "self._prompt_login") for stmt in node.body):
            continue
        if not any(dotted(handler.type) == "Exception" for handler in node.handlers):
            continue
        matches.append(node)
    assert len(matches) == 1, [getattr(node, "lineno", None) for node in matches]
    return matches[0]


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    assert "except _SpinaStartupCancelled:" not in text, "Cancellation re-raise already present"
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    tree = ast.parse(text)
    login_try = find_login_try(tree)

    broad = next(handler for handler in login_try.handlers if dotted(handler.type) == "Exception")
    line = lines[broad.lineno - 1]
    indent = line[: len(line) - len(line.lstrip())]
    assert line.strip().startswith("except Exception")
    lines[broad.lineno - 1 : broad.lineno - 1] = [
        f"{indent}except _SpinaStartupCancelled:",
        f"{indent}    raise",
    ]

    updated = newline.join(lines) + (newline if text.endswith(("\n", "\r\n")) else "")
    parsed = ast.parse(updated)
    repaired_try = find_login_try(parsed)
    handler_names = [dotted(handler.type) for handler in repaired_try.handlers]
    assert handler_names[:2] == ["_SpinaStartupCancelled", "Exception"], handler_names
    assert len(repaired_try.handlers[0].body) == 1
    assert isinstance(repaired_try.handlers[0].body[0], ast.Raise)
    assert repaired_try.handlers[0].body[0].exc is None
    DESKTOP.write_text(updated, encoding="utf-8", newline="")

    test = TEST.read_text(encoding="utf-8")
    marker = '''    raised = branch.body[raise_index].exc
    assert isinstance(raised, ast.Call) and dotted(raised.func) == "_SpinaStartupCancelled"

'''
    addition = '''    raised = branch.body[raise_index].exc
    assert isinstance(raised, ast.Call) and dotted(raised.func) == "_SpinaStartupCancelled"

    # The login try must re-raise startup cancellation before its broad Exception fallback.
    login_tries = []
    for node in ast.walk(app_init):
        if not isinstance(node, ast.Try):
            continue
        if not any(
            isinstance(call, ast.Call) and dotted(call.func) == "self._prompt_login"
            for stmt in node.body
            for call in ast.walk(stmt)
        ):
            continue
        login_tries.append(node)
    assert len(login_tries) == 1, [node.lineno for node in login_tries]
    login_try = login_tries[0]
    handler_names = [dotted(handler.type) for handler in login_try.handlers]
    assert handler_names[:2] == ["_SpinaStartupCancelled", "Exception"], handler_names
    startup_handler = login_try.handlers[0]
    assert len(startup_handler.body) == 1
    assert isinstance(startup_handler.body[0], ast.Raise)
    assert startup_handler.body[0].exc is None

'''
    assert test.count(marker) == 1
    test = test.replace(marker, addition)
    TEST.write_text(test, encoding="utf-8")
    print("Prepared Wave 46 cancellation re-raise repair.")


if __name__ == "__main__":
    main()
