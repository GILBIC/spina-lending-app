from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
DATA_BANK_FEATURE = ROOT / "spina_app" / "features" / "data_bank.py"
WAVE82_INSTALL_MARKER = "# --- BEGIN: Data Bank feature installer Wave 82 ---"
WRAPPER_HASHES = {'_spina_app_init_with_dashboard': '1ef876d8fe7e09f7bb2e35f13ec0b50403a87b321e11b81e059ad7799982cc50', '_spina_app_init_with_cash_control': 'cde95ced05cddfd8dbf68ed2ca93af2de90975d586ca3de76947ea997eb48bf8', '_spina_app_init_with_client_info_logs': 'b21819a83b5f7df417f3868817fd2b1a43c54d7c113ac1425001094ae71a5f02', '_spina_app_init_with_auto_close': 'ff1f545b3ee6c91c5380dd5c1ea5945c288ccf8c15d0dc3909769f6d666a5d30', '_spina_v13_app_init': 'bc37bc01645181f973f2e44556ecc60502e337419fdce2aeea4940b8e8e47f3b'}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized_hash(source: str) -> str:
    return hashlib.sha256("\n".join(line.rstrip() for line in source.strip().splitlines()).encode("utf-8")).hexdigest()


def _verify_wave82_auto_close_wrapper() -> None:
    feature_text = DATA_BANK_FEATURE.read_text(encoding="utf-8")
    feature_tree = ast.parse(feature_text)
    wrappers = [
        node
        for node in ast.walk(feature_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_wave82_app_init"
    ]
    assert len(wrappers) == 1, len(wrappers)
    wrapper = wrappers[0]
    assert wrapper.body, "Wave 82 startup wrapper is empty"

    first_calls = [
        call
        for call in ast.walk(wrapper.body[0])
        if isinstance(call, ast.Call)
    ]
    assert any(dotted(call.func) == "original_init" for call in first_calls), [
        dotted(call.func) for call in first_calls
    ]

    schedule_calls = [
        call
        for statement in wrapper.body[1:]
        for call in ast.walk(statement)
        if isinstance(call, ast.Call) and dotted(call.func) == "self._schedule_auto_daily_close"
    ]
    assert len(schedule_calls) == 1, len(schedule_calls)

    # Startup cancellation raised by original_init must propagate before the
    # auto-close try/except can run. Only scheduling errors are handled locally.
    assert isinstance(wrapper.body[0], ast.Expr)
    assert any(isinstance(statement, ast.Try) for statement in wrapper.body[1:])


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
        matches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        if matches:
            assert len(matches) == 1, (name, len(matches))
            source = ast.get_source_segment(text, matches[0])
            assert source is not None
            assert normalized_hash(source) == expected, (name, normalized_hash(source), expected)
            continue
        if name == "_spina_app_init_with_auto_close" and WAVE82_INSTALL_MARKER in text:
            _verify_wave82_auto_close_wrapper()
            continue
        raise AssertionError(f"Missing startup wrapper {name!r}")

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
