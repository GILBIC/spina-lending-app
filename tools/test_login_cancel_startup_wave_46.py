from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
WRAPPER_HASHES = {
    "_spina_app_init_with_dashboard": "1ef876d8fe7e09f7bb2e35f13ec0b50403a87b321e11b81e059ad7799982cc50",
    "_spina_app_init_with_cash_control": "cde95ced05cddfd8dbf68ed2ca93af2de90975d586ca3de76947ea997eb48bf8",
    "_spina_app_init_with_client_info_logs": "b21819a83b5f7df417f3868817fd2b1a43c54d7c113ac1425001094ae71a5f02",
    "_spina_app_init_with_auto_close": "ff1f545b3ee6c91c5380dd5c1ea5945c288ccf8c15d0dc3909769f6d666a5d30",
}
MODULAR_WRAPPERS = {
    "_spina_app_init_with_dashboard": (
        ROOT / "spina_app" / "features" / "dashboard.py",
        "init_with_dashboard",
        "self._build_dashboard_tab",
    ),
    "_spina_app_init_with_cash_control": (
        ROOT / "spina_app" / "features" / "cash_control.py",
        "init_with_cash_control",
        "self._build_cash_control_tab",
    ),
    "_spina_app_init_with_client_info_logs": (
        ROOT / "spina_app" / "features" / "client_info_logs.py",
        "init_with_client_info_logs",
        "self._build_client_info_logs_tab",
    ),
    "_spina_app_init_with_auto_close": (
        ROOT / "spina_app" / "features" / "data_bank.py",
        "_wave82_app_init",
        "self._schedule_auto_daily_close",
    ),
    "_spina_v13_app_init": (
        ROOT / "spina_app" / "features" / "side_navigation.py",
        "init_with_side_navigation",
        "self._rebuild_side_nav",
    ),
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized_hash(source: str) -> str:
    return hashlib.sha256(
        "\n".join(line.rstrip() for line in source.strip().splitlines()).encode("utf-8")
    ).hexdigest()


def verify_modular_wrapper(legacy_name: str) -> None:
    module_path, wrapper_name, required_post_init_call = MODULAR_WRAPPERS[legacy_name]
    module_text = module_path.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    wrappers = [
        node
        for node in ast.walk(module_tree)
        if isinstance(node, ast.FunctionDef) and node.name == wrapper_name
    ]
    assert len(wrappers) == 1, (legacy_name, wrapper_name, len(wrappers))
    wrapper = wrappers[0]
    assert wrapper.body, (legacy_name, "empty wrapper")

    # The wrapped App.__init__ call must stay outside every local try/except. If
    # login cancellation raises here, post-startup feature work is never entered.
    first_statement = wrapper.body[0]
    assert isinstance(first_statement, ast.Expr), (legacy_name, type(first_statement).__name__)
    first_calls = [
        call for call in ast.walk(first_statement) if isinstance(call, ast.Call)
    ]
    assert any(dotted(call.func) == "original_init" for call in first_calls), (
        legacy_name,
        [dotted(call.func) for call in first_calls],
    )

    post_init_calls = [
        dotted(call.func)
        for statement in wrapper.body[1:]
        for call in ast.walk(statement)
        if isinstance(call, ast.Call)
    ]
    assert required_post_init_call in post_init_calls, (
        legacy_name,
        required_post_init_call,
        post_init_calls,
    )
    assert any(isinstance(statement, ast.Try) for statement in wrapper.body[1:]), (
        legacy_name,
        "post-init work is not guarded",
    )


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)

    exception = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_SpinaStartupCancelled"
    )
    assert [dotted(base) for base in exception.bases] == ["Exception"]

    app = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    app_init = next(
        node
        for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    cancel_branches = []
    for node in ast.walk(app_init):
        if not isinstance(node, ast.If):
            continue
        body_calls = [
            dotted(call.func)
            for stmt in node.body
            for call in ast.walk(stmt)
            if isinstance(call, ast.Call)
        ]
        raises = [stmt for stmt in node.body if isinstance(stmt, ast.Raise)]
        if "self._destroy_root_safely" in body_calls and raises:
            cancel_branches.append(node)
    assert len(cancel_branches) == 1, [node.lineno for node in cancel_branches]
    branch = cancel_branches[0]
    destroy_index = next(
        i
        for i, stmt in enumerate(branch.body)
        if any(
            isinstance(call, ast.Call)
            and dotted(call.func) == "self._destroy_root_safely"
            for call in ast.walk(stmt)
        )
    )
    raise_index = next(
        i for i, stmt in enumerate(branch.body) if isinstance(stmt, ast.Raise)
    )
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

    main_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    guarded = []
    for node in ast.walk(main_fn):
        if not isinstance(node, ast.Try):
            continue
        if not any(
            isinstance(call, ast.Call) and dotted(call.func) == "App"
            for stmt in node.body
            for call in ast.walk(stmt)
        ):
            continue
        for handler in node.handlers:
            if dotted(handler.type) == "_SpinaStartupCancelled":
                assert any(isinstance(stmt, ast.Return) for stmt in handler.body)
                guarded.append(node)
    assert len(guarded) == 1, len(guarded)

    all_wrappers = set(WRAPPER_HASHES) | set(MODULAR_WRAPPERS)
    for name in all_wrappers:
        matches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        if matches:
            assert name in WRAPPER_HASHES, (name, "unexpected legacy wrapper remains")
            assert len(matches) == 1, (name, len(matches))
            source = ast.get_source_segment(text, matches[0])
            assert source is not None
            expected = WRAPPER_HASHES[name]
            assert normalized_hash(source) == expected, (
                name,
                normalized_hash(source),
                expected,
            )
            continue
        verify_modular_wrapper(name)

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
