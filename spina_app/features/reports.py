"""Complete Reports feature installer for SPINA Wave 80."""
from __future__ import annotations

from typing import Any, Mapping

from spina_app import client_statement_generation as _generation
from spina_app import report_controller as _controller
from spina_app import report_engine as _engine
from spina_app.reports_tab_presentation import (
    configure_reports_tab_dependencies,
    _build_reports_tab,
)

_REPORTS_REQUIRED_APP_METHODS = (
    "_build_reports_tab",
    "generate_pdf_selected",
    "refresh_reports",
    "open_report_generation_log",
)


def _safe_log(callback, context: str, exc: BaseException | None = None) -> None:
    if not callable(callback):
        return
    try:
        callback(context, exc)
    except Exception:
        pass


def _reports_install_complete(app_class: type) -> bool:
    return all(callable(getattr(app_class, name, None)) for name in _REPORTS_REQUIRED_APP_METHODS)


def _with_modular_fallbacks(namespace: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve Reports dependencies without relying on desktop installer order."""
    dependencies = dict(namespace)

    if dependencies.get("_spina__client_due_meta") is None:
        try:
            from spina_app.services import clients as _client_services

            _client_services.configure_client_service_dependencies(dependencies)
            dependencies["_spina__client_due_meta"] = _client_services._spina__client_due_meta
        except Exception:
            pass

    if dependencies.get("_spina__fmt_client_money") is None:
        try:
            from spina_app.utilities.formatting import _spina_v23_money

            dependencies["_spina__fmt_client_money"] = _spina_v23_money
        except Exception:
            pass

    return dependencies


def install_reports_feature(
    app_class: type | None,
    *,
    namespace: Mapping[str, Any],
    log_exc=None,
    log_suppressed_once=None,
) -> bool:
    """Install all active Reports methods exactly once.

    A stale installed marker is repaired when required App methods are missing.
    This protects startup when another feature's dependencies are installed later.
    """
    if app_class is None:
        return False
    if bool(getattr(app_class, "_spina_reports_wave80_installed", False)) and _reports_install_complete(app_class):
        return True

    # A previous partial installation must not block a complete retry.
    try:
        app_class._spina_reports_wave80_installed = False
    except Exception:
        pass

    try:
        dependencies = _with_modular_fallbacks(namespace)
        _engine.configure_report_engine_dependencies(dependencies)
        dependencies.update(
            {
                "generate_client_pdf": _engine.generate_client_pdf,
                "REPORT_GENERATION_COUNT_FILE": _engine.REPORT_GENERATION_COUNT_FILE,
                "REPORT_GENERATION_LOG_FILE": _engine.REPORT_GENERATION_LOG_FILE,
                "REPORT_GENERATION_LOG_CSV": _engine.REPORT_GENERATION_LOG_CSV,
                "_spina_record_report_generation": _engine._spina_record_report_generation,
            }
        )
        missing_controller = _controller.configure_report_controller_dependencies(dependencies)
        configure_reports_tab_dependencies(dependencies)
        _generation.configure_client_statement_generation_dependencies(dependencies)
        if missing_controller:
            raise RuntimeError(
                "Reports controller dependencies unavailable: "
                + ", ".join(missing_controller)
            )

        app_class._build_reports_tab = _build_reports_tab
        app_class.generate_pdf_selected = _generation.generate_pdf_selected
        for name, value in _controller.REPORT_CONTROLLER_METHODS.items():
            setattr(app_class, name, value)

        # Preserve compatibility for callers that still resolve report helpers from
        # the desktop entry module while keeping their implementation modular.
        try:
            namespace["generate_client_pdf"] = _engine.generate_client_pdf
            namespace["REPORT_GENERATION_COUNT_FILE"] = _engine.REPORT_GENERATION_COUNT_FILE
            namespace["REPORT_GENERATION_LOG_FILE"] = _engine.REPORT_GENERATION_LOG_FILE
            namespace["REPORT_GENERATION_LOG_CSV"] = _engine.REPORT_GENERATION_LOG_CSV
            namespace["_spina_record_report_generation"] = _engine._spina_record_report_generation
        except Exception:
            pass

        app_class._spina_reports_wave80_installed = True
        return True
    except Exception as exc:
        try:
            app_class._spina_reports_wave80_installed = False
        except Exception:
            pass
        try:
            if callable(log_suppressed_once):
                log_suppressed_once(
                    "reports_wave80_install_failed",
                    "Wave 80 Reports installation failed",
                    exc,
                )
        except Exception:
            pass
        _safe_log(log_exc, "reports.wave80.install", exc)
        return False
