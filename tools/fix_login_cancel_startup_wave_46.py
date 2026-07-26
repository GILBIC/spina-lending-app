from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TEST = ROOT / "tools/test_login_cancel_startup_wave_46.py"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized_hash(source: str) -> str:
    return hashlib.sha256("\n".join(line.rstrip() for line in source.strip().splitlines()).encode("utf-8")).hexdigest()


def source_segment(text: str, node: ast.AST) -> str:
    value = ast.get_source_segment(text, node)
    assert value is not None
    return value


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    if "class _SpinaStartupCancelled(Exception):" in text:
        raise AssertionError("Wave 46 login-cancel repair already present")

    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    tree = ast.parse(text)

    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_init = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    main_fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")

    wrapper_names = (
        "_spina_app_init_with_dashboard",
        "_spina_app_init_with_cash_control",
        "_spina_app_init_with_client_info_logs",
        "_spina_app_init_with_auto_close",
        "_spina_v13_app_init",
    )
    wrapper_hashes: dict[str, str] = {}
    for name in wrapper_names:
        matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(matches) == 1, (name, len(matches))
        wrapper_hashes[name] = normalized_hash(source_segment(text, matches[0]))

    cancel_branches = []
    for node in ast.walk(app_init):
        if not isinstance(node, ast.If):
            continue
        body_calls = [call for stmt in node.body for call in ast.walk(stmt) if isinstance(call, ast.Call)]
        destroy = next((call for call in body_calls if dotted(call.func) in {"self._destroy_root_safely", "root.destroy", "self.root.destroy"}), None)
        returns = [stmt for stmt in node.body if isinstance(stmt, ast.Return)]
        if destroy is not None and returns:
            cancel_branches.append((node, destroy, returns[-1]))

    assert len(cancel_branches) == 1, [(node.lineno, dotted(destroy.func), ret.lineno) for node, destroy, ret in cancel_branches]
    login_if, safe_destroy_call, cancel_return = cancel_branches[0]
    assert dotted(safe_destroy_call.func) == "self._destroy_root_safely", dotted(safe_destroy_call.func)
    assert cancel_return.value is None

    app_calls = [node for node in ast.walk(main_fn) if isinstance(node, ast.Call) and dotted(node.func) == "App"]
    assert len(app_calls) == 1, len(app_calls)
    app_call = app_calls[0]
    assignment = None
    for node in ast.walk(main_fn):
        if isinstance(node, ast.Assign) and app_call in list(ast.walk(node.value)):
            assignment = node
            break
    assert assignment is not None, "app = App(root) assignment not found"
    assert len(assignment.targets) == 1 and isinstance(assignment.targets[0], ast.Name)
    assert assignment.targets[0].id == "app"

    exception_lines = [
        "class _SpinaStartupCancelled(Exception):",
        "    \"\"\"Internal signal used to stop layered App initialization after login cancellation.\"\"\"",
        "    pass",
        "",
        "",
    ]

    return_line = lines[cancel_return.lineno - 1]
    return_indent = return_line[: len(return_line) - len(return_line.lstrip())]
    assert return_line.strip() == "return"
    lines[cancel_return.lineno - 1 : cancel_return.lineno] = [f"{return_indent}raise _SpinaStartupCancelled()"]

    assignment_line = lines[assignment.lineno - 1]
    assignment_indent = assignment_line[: len(assignment_line) - len(assignment_line.lstrip())]
    assert assignment_line.strip() == "app = App(root)"
    assignment_replacement = [
        f"{assignment_indent}try:",
        f"{assignment_indent}    app = App(root)",
        f"{assignment_indent}except _SpinaStartupCancelled:",
        f"{assignment_indent}    return",
    ]
    lines[assignment.lineno - 1 : assignment.lineno] = assignment_replacement

    main_index = next(i for i, line in enumerate(lines) if line.startswith("def main(") or line == "def main():")
    lines[main_index:main_index] = exception_lines

    updated = newline.join(lines) + (newline if text.endswith(("\n", "\r\n")) else "")
    ast.parse(updated)
    assert updated.count("class _SpinaStartupCancelled(Exception):") == 1
    assert updated.count("raise _SpinaStartupCancelled()") == 1
    assert updated.count("except _SpinaStartupCancelled:") == 1
    assert updated.index("self._destroy_root_safely()") < updated.index("raise _SpinaStartupCancelled()")
    DESKTOP.write_text(updated, encoding="utf-8", newline="")

    test_text = textwrap.dedent(
        f'''\
        from __future__ import annotations

        import ast
        import hashlib
        from pathlib import Path

        ROOT = Path(__file__).resolve().parents[1]
        DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
        WRAPPER_HASHES = {wrapper_hashes!r}


        def dotted(node: ast.AST) -> str:
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                left = dotted(node.value)
                return f"{{left}}.{{node.attr}}" if left else node.attr
            return ""


        def normalized_hash(source: str) -> str:
            return hashlib.sha256("\\n".join(line.rstrip() for line in source.strip().splitlines()).encode("utf-8")).hexdigest()


        def main() -> None:
            text = DESKTOP.read_text(encoding="utf-8")
            tree = ast.parse(text)

            exception = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_SpinaStartupCancelled")
            assert [dotted(base) for base in exception.bases] == ["Exception"]

            app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
            app_init = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
            cancel_branches = []
            for node in ast.walk(app_init):
                if not isinstance(node, ast.If):
                    continue
                body_calls = [dotted(call.func) for stmt in node.body for call in ast.walk(stmt) if isinstance(call, ast.Call)]
                raises = [stmt for stmt in node.body if isinstance(stmt, ast.Raise)]
                if "self._destroy_root_safely" in body_calls and raises:
                    cancel_branches.append(node)
            assert len(cancel_branches) == 1, [node.lineno for node in cancel_branches]
            branch = cancel_branches[0]
            destroy_index = next(i for i, stmt in enumerate(branch.body) if any(isinstance(call, ast.Call) and dotted(call.func) == "self._destroy_root_safely" for call in ast.walk(stmt)))
            raise_index = next(i for i, stmt in enumerate(branch.body) if isinstance(stmt, ast.Raise))
            assert destroy_index < raise_index
            raised = branch.body[raise_index].exc
            assert isinstance(raised, ast.Call) and dotted(raised.func) == "_SpinaStartupCancelled"

            main_fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
            guarded = []
            for node in ast.walk(main_fn):
                if not isinstance(node, ast.Try):
                    continue
                if not any(isinstance(call, ast.Call) and dotted(call.func) == "App" for stmt in node.body for call in ast.walk(stmt)):
                    continue
                for handler in node.handlers:
                    if dotted(handler.type) == "_SpinaStartupCancelled":
                        assert any(isinstance(stmt, ast.Return) for stmt in handler.body)
                        guarded.append(node)
            assert len(guarded) == 1, len(guarded)

            for name, expected in WRAPPER_HASHES.items():
                node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
                source = ast.get_source_segment(text, node)
                assert source is not None
                assert normalized_hash(source) == expected, (name, normalized_hash(source), expected)

            events = []

            class StartupCancelled(Exception):
                pass

            def base_init():
                events.append("safe_destroy")
                raise StartupCancelled()

            def client_logs_wrapper():
                base_init()
                events.append("client_info_logs")

            def outer_wrapper():
                client_logs_wrapper()
                events.append("outer")

            try:
                outer_wrapper()
            except StartupCancelled:
                pass
            assert events == ["safe_destroy"], events

            print("Wave 46 login-cancel startup regression passed.")


        if __name__ == "__main__":
            main()
        '''
    )
    TEST.write_text(test_text, encoding="utf-8")
    print("Prepared guarded Wave 46 login-cancel startup repair and regression.")


if __name__ == "__main__":
    main()
