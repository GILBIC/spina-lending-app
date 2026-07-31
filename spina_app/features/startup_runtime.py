"""Final desktop startup runtime ownership for SPINA Wave 89."""
from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any

RootFactory = Callable[[], Any]
SuppressedLogCallback = Callable[[str, str, BaseException | None], Any]


def _safe_suppressed_log(
    callback: SuppressedLogCallback | None,
    key: str,
    message: str,
    exc: BaseException | None = None,
) -> None:
    if not callable(callback):
        return
    try:
        callback(key, message, exc)
    except Exception:
        pass


def _default_root_factory():
    import tkinter as tk

    return tk.Tk()


def _is_startup_cancelled(exc: BaseException, cancellation_type: object) -> bool:
    return (
        isinstance(cancellation_type, type)
        and issubclass(cancellation_type, BaseException)
        and isinstance(exc, cancellation_type)
    )


def run_desktop_application(
    app_class: object,
    *,
    startup_cancelled_cls: object = None,
    root_factory: RootFactory | None = None,
    attach_direct_integration: Callable[[Any], Any] | None = None,
    log_suppressed_once: SuppressedLogCallback | None = None,
):
    """Create the Tk root, build the app, attach integration, and enter mainloop."""
    if not callable(app_class):
        raise TypeError("SPINA App class is not callable.")

    factory = root_factory if callable(root_factory) else _default_root_factory
    root = factory()

    try:
        app = app_class(root)
    except Exception as exc:
        if _is_startup_cancelled(exc, startup_cancelled_cls):
            return None
        raise

    if callable(attach_direct_integration):
        try:
            attach_direct_integration(app)
        except Exception as exc:
            _safe_suppressed_log(
                log_suppressed_once,
                "startup_runtime_wave89_attach",
                "Wave 89 direct integration attachment failed",
                exc,
            )

    mainloop = getattr(root, "mainloop", None)
    if not callable(mainloop):
        raise RuntimeError("SPINA root does not provide mainloop().")
    mainloop()
    return app


def install_startup_runtime(
    namespace: MutableMapping[str, object] | None,
    *,
    root_factory: RootFactory | None = None,
) -> bool:
    """Replace the module-level main function with one final late runtime owner."""
    if not isinstance(namespace, MutableMapping):
        return False
    if bool(namespace.get("_spina_startup_runtime_wave89_installed")):
        return True

    original_main = namespace.get("main")

    def main():
        return run_desktop_application(
            namespace.get("App"),
            startup_cancelled_cls=namespace.get("_SpinaStartupCancelled"),
            root_factory=root_factory,
            attach_direct_integration=namespace.get("attach_direct_integration"),
            log_suppressed_once=namespace.get("_log_suppressed_once"),
        )

    namespace["_spina_startup_runtime_wave89_original_main"] = original_main
    namespace["main"] = main
    namespace["_spina_startup_runtime_wave89_installed"] = True
    return namespace.get("main") is main
