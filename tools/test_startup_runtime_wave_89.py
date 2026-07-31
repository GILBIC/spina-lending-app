#!/usr/bin/env python3
"""Regression coverage for final desktop startup ownership Wave 89."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app.features.startup_runtime import (
    install_startup_runtime,
    run_desktop_application,
)

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
HEADER = ROOT / "spina_app" / "account_header_presentation.py"
SHELL = ROOT / "spina_app" / "features" / "application_shell.py"
FEATURE = ROOT / "spina_app" / "features" / "startup_runtime.py"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def check_architecture() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")
    shell_text = SHELL.read_text(encoding="utf-8")
    feature_text = FEATURE.read_text(encoding="utf-8")

    desktop_tree = ast.parse(desktop_text, filename=str(DESKTOP))
    top_level_main = [
        node for node in desktop_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    assert len(top_level_main) <= 1

    final_calls = []
    for node in desktop_tree.body:
        if not isinstance(node, ast.If):
            continue
        calls = [
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
        ]
        if "main" in calls:
            final_calls.append(node)
    assert len(final_calls) == 1, [node.lineno for node in final_calls]

    configure_marker = "_wave46_configure_account_header_dependencies(globals())"
    assert desktop_text.count(configure_marker) == 1
    assert desktop_text.index(configure_marker) < desktop_text.index("if __name__ == '__main__':\n    main()")

    configure_tree = ast.parse(header_text, filename=str(HEADER))
    configure = next(
        node for node in configure_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "configure_account_header_dependencies"
    )
    configure_source = ast.get_source_segment(header_text, configure) or ""
    assert "install_application_shell" in configure_source
    assert "install_startup_runtime" not in configure_source

    shell_tree = ast.parse(shell_text, filename=str(SHELL))
    shell_installer = next(
        node for node in shell_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "install_application_shell"
    )
    shell_source = ast.get_source_segment(shell_text, shell_installer) or ""
    assert "install_startup_runtime" in shell_source
    assert "startup_installer(namespace)" in shell_source
    assert "startup_runtime_wave89_install" in shell_source
    assert shell_source.index("accounts_installer(") < shell_source.index(
        "side_navigation_installer("
    )
    assert shell_source.index("side_navigation_installer(") < shell_source.index(
        "startup_installer(namespace)"
    )

    feature_tree = ast.parse(feature_text, filename=str(FEATURE))
    names = {
        node.name
        for node in feature_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {"run_desktop_application", "install_startup_runtime"} <= names

    lowered = feature_text.lower()
    for forbidden in (
        "insert into",
        "update ",
        "delete from",
        "create table",
        ".commit(",
        ".rollback(",
        "write_text(",
        "write_bytes(",
        ".unlink(",
    ):
        assert forbidden not in lowered, forbidden


def check_runtime() -> None:
    events: list[object] = []
    logs: list[tuple[str, str, str]] = []

    class Root:
        def mainloop(self):
            events.append("mainloop")

    class App:
        def __init__(self, root):
            self.root = root
            events.append("app")

    app = run_desktop_application(
        App,
        root_factory=Root,
        attach_direct_integration=lambda instance: events.append(
            ("attach", instance.root.__class__.__name__)
        ),
    )
    assert isinstance(app, App)
    assert events == ["app", ("attach", "Root"), "mainloop"]
    events.clear()

    class StartupCancelled(Exception):
        pass

    class CancelApp:
        def __init__(self, root):
            events.append("cancel")
            raise StartupCancelled()

    assert run_desktop_application(
        CancelApp,
        startup_cancelled_cls=StartupCancelled,
        root_factory=Root,
        attach_direct_integration=lambda instance: events.append("unexpected-attach"),
    ) is None
    assert events == ["cancel"]
    events.clear()

    def broken_attach(instance):
        events.append("attach-attempt")
        raise RuntimeError("attach failed")

    app = run_desktop_application(
        App,
        root_factory=Root,
        attach_direct_integration=broken_attach,
        log_suppressed_once=lambda key, message, exc=None: logs.append(
            (key, message, type(exc).__name__)
        ),
    )
    assert isinstance(app, App)
    assert events == ["app", "attach-attempt", "mainloop"]
    assert logs == [
        (
            "startup_runtime_wave89_attach",
            "Wave 89 direct integration attachment failed",
            "RuntimeError",
        )
    ]
    events.clear()

    class BrokenApp:
        def __init__(self, root):
            raise ValueError("unexpected")

    try:
        run_desktop_application(
            BrokenApp,
            startup_cancelled_cls=StartupCancelled,
            root_factory=Root,
        )
    except ValueError as exc:
        assert str(exc) == "unexpected"
    else:
        raise AssertionError("unexpected startup error was swallowed")

    original_main = lambda: "legacy-main"
    namespace: dict[str, object] = {
        "main": original_main,
        "App": App,
        "_SpinaStartupCancelled": StartupCancelled,
        "attach_direct_integration": lambda instance: events.append("dynamic-attach"),
    }
    assert install_startup_runtime(namespace, root_factory=Root)
    installed_main = namespace["main"]
    assert callable(installed_main)
    assert namespace["_spina_startup_runtime_wave89_original_main"] is original_main
    assert namespace["_spina_startup_runtime_wave89_installed"] is True
    assert installed_main() is not None
    assert events == ["app", "dynamic-attach", "mainloop"]

    assert install_startup_runtime(namespace, root_factory=Root)
    assert namespace["main"] is installed_main

    class ReplacementApp(App):
        def __init__(self, root):
            super().__init__(root)
            events.append("replacement")

    events.clear()
    namespace["App"] = ReplacementApp
    assert installed_main() is not None
    assert events == ["app", "replacement", "dynamic-attach", "mainloop"]


def main() -> None:
    check_architecture()
    check_runtime()
    print("Wave 89 startup runtime regression passed.")


if __name__ == "__main__":
    main()
