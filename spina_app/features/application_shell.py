"""Final account, sidebar, and startup installer for SPINA Wave 92."""
from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any

Installer = Callable[..., object]
LogCallback = Callable[[str, str, BaseException | None], Any]


def _safe_install_log(
    namespace: MutableMapping[str, object],
    key: str,
    message: str,
    exc: BaseException,
) -> None:
    callback = namespace.get("_log_suppressed_once")
    if not callable(callback):
        return
    try:
        callback(key, message, exc)
    except Exception:
        pass


def install_application_shell(
    namespace: MutableMapping[str, object] | None,
    *,
    presentation_namespace: MutableMapping[str, object] | None = None,
    refresh_header: Callable[..., object] | None = None,
    build_header: Callable[..., object] | None = None,
    account_display_name: Callable[..., object] | None = None,
    accounts_installer: Installer | None = None,
    side_navigation_installer: Installer | None = None,
    startup_installer: Installer | None = None,
) -> dict[str, bool]:
    """Install final application-shell boundaries in dependency order.

    Each boundary is isolated so an account installation failure does not block
    sidebar or startup ownership. Component installers remain responsible for
    their own idempotence.
    """
    results = {"accounts": False, "side_navigation": False, "startup": False}
    if not isinstance(namespace, MutableMapping):
        return results

    app_class = namespace.get("App")

    try:
        if account_display_name is None or accounts_installer is None:
            from spina_app.features.accounts import (
                account_display_name as default_account_display_name,
                install_accounts_feature,
            )

            if account_display_name is None:
                account_display_name = default_account_display_name
            if accounts_installer is None:
                accounts_installer = install_accounts_feature

        target = (
            presentation_namespace
            if isinstance(presentation_namespace, MutableMapping)
            else namespace
        )
        target["_spina_v32_account_display_name"] = account_display_name
        results["accounts"] = bool(
            accounts_installer(
                app_class,
                namespace=namespace,
                refresh_header=refresh_header,
                build_header=build_header,
            )
        )
    except Exception as exc:
        _safe_install_log(
            namespace,
            "accounts_wave83_install",
            "Wave 83 accounts feature installation failed",
            exc,
        )

    try:
        if side_navigation_installer is None:
            from spina_app.features.side_navigation import (
                install_side_navigation_feature,
            )

            side_navigation_installer = install_side_navigation_feature

        results["side_navigation"] = bool(
            side_navigation_installer(
                app_class,
                namespace=namespace,
                log_suppressed_once=namespace.get("_log_suppressed_once"),
            )
        )
    except Exception as exc:
        _safe_install_log(
            namespace,
            "side_navigation_wave86_install",
            "Wave 86 side-navigation installation failed",
            exc,
        )

    try:
        if startup_installer is None:
            from spina_app.features.startup_runtime import install_startup_runtime

            startup_installer = install_startup_runtime

        results["startup"] = bool(startup_installer(namespace))
    except Exception as exc:
        _safe_install_log(
            namespace,
            "startup_runtime_wave89_install",
            "Wave 89 startup runtime installation failed",
            exc,
        )

    namespace["_spina_application_shell_wave92_results"] = dict(results)
    namespace["_spina_application_shell_wave92_installed"] = all(results.values())
    return results
