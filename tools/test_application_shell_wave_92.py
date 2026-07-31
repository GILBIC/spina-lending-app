#!/usr/bin/env python3
"""Regression coverage for the final application-shell installer Wave 92."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app.features.application_shell import install_application_shell

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
HEADER = ROOT / "spina_app" / "account_header_presentation.py"
SHELL = ROOT / "spina_app" / "features" / "application_shell.py"


def function_source(text: str, name: str) -> str:
    tree = ast.parse(text)
    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1, (name, len(matches))
    return ast.get_source_segment(text, matches[0]) or ""


def check_architecture() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")
    shell_text = SHELL.read_text(encoding="utf-8")

    assert desktop_text.count("_wave46_configure_account_header_dependencies(globals())") == 1

    configure_source = function_source(
        header_text,
        "configure_account_header_dependencies",
    )
    assert "install_application_shell" in configure_source
    assert "presentation_namespace=globals()" in configure_source
    assert 'refresh_header=globals().get("_spina_v32_refresh_user_header")' in configure_source
    assert 'build_header=globals().get("_spina_v32_build_header")' in configure_source
    assert "application_shell_wave92_install" in configure_source
    for removed_direct_installer in (
        "install_accounts_feature",
        "install_side_navigation_feature",
        "install_startup_runtime",
    ):
        assert removed_direct_installer not in configure_source

    installer_source = function_source(shell_text, "install_application_shell")
    for token in (
        "install_accounts_feature",
        "install_side_navigation_feature",
        "install_startup_runtime",
        '"accounts_wave83_install"',
        '"side_navigation_wave86_install"',
        '"startup_runtime_wave89_install"',
        'namespace["_spina_application_shell_wave92_results"]',
        'namespace["_spina_application_shell_wave92_installed"]',
    ):
        assert token in installer_source, token

    assert installer_source.index("accounts_installer(") < installer_source.index(
        "side_navigation_installer("
    )
    assert installer_source.index("side_navigation_installer(") < installer_source.index(
        "startup_installer(namespace)"
    )

    lowered = shell_text.lower()
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
    presentation: dict[str, object] = {}

    class App:
        pass

    def display_name(app, username):
        return f"display:{username}"

    def refresh_header(self):
        return None

    def build_header(self, *args, **kwargs):
        return None

    def install_accounts(app_class, **kwargs):
        assert app_class is App
        assert kwargs["namespace"] is namespace
        assert kwargs["refresh_header"] is refresh_header
        assert kwargs["build_header"] is build_header
        events.append("accounts")
        return True

    def install_sidebar(app_class, **kwargs):
        assert app_class is App
        assert kwargs["namespace"] is namespace
        assert kwargs["log_suppressed_once"] is namespace["_log_suppressed_once"]
        events.append("side_navigation")
        return True

    def install_startup(received_namespace):
        assert received_namespace is namespace
        events.append("startup")
        return True

    namespace: dict[str, object] = {
        "App": App,
        "_log_suppressed_once": lambda key, message, exc=None: logs.append(
            (key, message, type(exc).__name__ if exc is not None else "")
        ),
    }
    results = install_application_shell(
        namespace,
        presentation_namespace=presentation,
        refresh_header=refresh_header,
        build_header=build_header,
        account_display_name=display_name,
        accounts_installer=install_accounts,
        side_navigation_installer=install_sidebar,
        startup_installer=install_startup,
    )
    assert results == {"accounts": True, "side_navigation": True, "startup": True}
    assert events == ["accounts", "side_navigation", "startup"]
    assert presentation["_spina_v32_account_display_name"] is display_name
    assert namespace["_spina_application_shell_wave92_results"] == results
    assert namespace["_spina_application_shell_wave92_installed"] is True
    assert logs == []

    events.clear()
    logs.clear()

    def broken_accounts(*args, **kwargs):
        events.append("accounts")
        raise RuntimeError("account failure")

    results = install_application_shell(
        namespace,
        presentation_namespace=presentation,
        account_display_name=display_name,
        accounts_installer=broken_accounts,
        side_navigation_installer=install_sidebar,
        startup_installer=install_startup,
    )
    assert results == {"accounts": False, "side_navigation": True, "startup": True}
    assert events == ["accounts", "side_navigation", "startup"]
    assert namespace["_spina_application_shell_wave92_installed"] is False
    assert logs == [
        (
            "accounts_wave83_install",
            "Wave 83 accounts feature installation failed",
            "RuntimeError",
        )
    ]

    assert install_application_shell(None) == {
        "accounts": False,
        "side_navigation": False,
        "startup": False,
    }


def main() -> None:
    check_architecture()
    check_runtime()
    print("Wave 92 application-shell regression passed.")


if __name__ == "__main__":
    main()
