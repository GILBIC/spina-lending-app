#!/usr/bin/env python3
"""Installer regressions for Client Info Logs Wave 78."""
from __future__ import annotations

from spina_app.features.client_info_logs import install_client_info_logs_feature


def test_installer_idempotence() -> None:
    calls: list[str] = []

    class DummyApp:
        def __init__(self, *_args, **_kwargs):
            calls.append("init")

        def refresh_clients(self, *_args, **_kwargs):
            calls.append("refresh_clients")
            return "refreshed"

    assert install_client_info_logs_feature(DummyApp)
    assert DummyApp._spina_client_info_logs_wave78_installed is True
    assert callable(DummyApp._build_client_info_logs_tab)
    assert callable(DummyApp.render_client_info_logs)
    assert callable(DummyApp.refresh_client_info_logs)
    assert callable(DummyApp._client_info_logs_fetch_rows)

    first_init = DummyApp.__init__
    first_refresh = DummyApp.refresh_clients
    instance = DummyApp()
    assert calls == ["init"]
    assert instance.refresh_clients() == "refreshed"
    assert calls[-1] == "refresh_clients"

    assert install_client_info_logs_feature(DummyApp)
    assert DummyApp.__init__ is first_init
    assert DummyApp.refresh_clients is first_refresh


def test_missing_app_class() -> None:
    assert install_client_info_logs_feature(None) is False


def main() -> None:
    test_installer_idempotence()
    test_missing_app_class()
    print("Wave 78 Client Info Logs installer tests passed.")


if __name__ == "__main__":
    main()
